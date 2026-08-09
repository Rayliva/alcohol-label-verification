"""The corpus catalogue is internally consistent — PRD → Test corpus.

These are cheap structural checks on the *declared* corpus, not on rendered
images. They exist because the expensive failure here is silent: a variant whose
expected verdicts were never written is a label that renders, scores nothing,
and makes coverage look better than it is.

Ground truth in this catalogue is declared by hand from the regulation, never
computed by the rule engine. Deriving the expectation from the code under test
would assert only that the code agrees with itself.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parents[3] / "corpus"
sys.path.insert(0, str(CORPUS.parent))

from corpus.generate import CATALOGUE, Variant  # noqa: E402
from corpus.render import GOVERNMENT_WARNING  # noqa: E402

from app.rules.beverage_types import rules_for  # noqa: E402
from app.rules.types import Verdict  # noqa: E402
from app.rules.warning import STATUTORY_WARNING  # noqa: E402


def curated() -> list[Variant]:
    """Tiers 1-5: the labels the accuracy target is measured against."""
    return [v for v in CATALOGUE if v.tier <= 5]


class TestStatutoryTextHasOneSource:
    def test_the_renderer_draws_the_same_warning_the_engine_checks(self) -> None:
        # Two copies of fifty words of statute is one edit away from a corpus
        # that asserts the opposite of what it claims.
        assert GOVERNMENT_WARNING == STATUTORY_WARNING


class TestIdentity:
    def test_every_label_id_is_unique(self) -> None:
        ids = [v.label_id for v in CATALOGUE]
        duplicates = [label_id for label_id, n in Counter(ids).items() if n > 1]
        assert not duplicates

    def test_every_label_explains_what_it_is_for(self) -> None:
        for variant in CATALOGUE:
            assert variant.notes, f"{variant.label_id} has no notes"


class TestExpectations:
    def test_every_curated_label_declares_a_verdict_for_every_checked_field(self) -> None:
        for variant in curated():
            if variant.expected_overall == "unreadable":
                continue  # nothing was read, so there is nothing to expect
            configured = {rule.field for rule in rules_for(variant.beverage_type).fields}
            missing = configured - set(variant.expected_fields) - {"country_of_origin"}
            assert not missing, f"{variant.label_id} declares no expectation for {missing}"

    def test_expected_verdicts_are_real_verdicts(self) -> None:
        allowed = {v.value for v in Verdict}
        for variant in CATALOGUE:
            for field, verdict in variant.expected_fields.items():
                assert verdict in allowed, f"{variant.label_id}.{field} = {verdict}"

    def test_expected_overall_is_the_worst_field_verdict(self) -> None:
        severity = {"pass": 0, "needs_review": 1, "fail": 2}
        for variant in curated():
            if variant.expected_overall == "unreadable":
                continue
            worst = max(variant.expected_fields.values(), key=lambda v: severity[v])
            assert variant.expected_overall == worst, variant.label_id

    def test_an_unreadable_label_is_never_also_a_failure(self) -> None:
        # "We could not read this" is not "this label is non-compliant".
        # Conflating them reports compliant labels as violations (PRD FR-3).
        for variant in CATALOGUE:
            if variant.expected_overall == "unreadable":
                assert not variant.expected_fields, variant.label_id


class TestOneViolationPerLabel:
    def test_a_violation_label_still_passes_its_untouched_fields(self) -> None:
        # This is how false positives get caught: if a label breaks one rule and
        # the tool flags three, the corpus says so.
        for variant in curated():
            if variant.expected_overall != "fail":
                continue
            failures = [f for f, v in variant.expected_fields.items() if v == "fail"]
            assert len(failures) <= 1, f"{variant.label_id} fails on {failures}"


class TestCoverage:
    def test_the_tier_counts_match_the_prd(self) -> None:
        counts = Counter(v.tier for v in CATALOGUE)
        assert counts[1] == 12, "tier 1: clean baseline"
        assert counts[2] == 28, "tier 2: single-field violations"
        assert counts[3] == 6, "tier 3: conditional rules"
        assert counts[4] == 12, "tier 4: image quality"
        assert counts[5] == 3, "tier 5: same field of vision"

    def test_the_curated_corpus_is_the_size_the_prd_promises(self) -> None:
        assert len(curated()) == 61

    def test_the_warning_gets_the_most_coverage_of_any_field(self) -> None:
        # It is the only exact check and has the most ways to fail.
        warning_labels = [v for v in CATALOGUE if v.tier == 2 and "warning" in v.label_id]
        assert len(warning_labels) == 8

    def test_tier_four_is_half_unreadable(self) -> None:
        # Testing only degraded-but-readable images rewards confident
        # hallucination. The other half must fail with a specific reason.
        tier_four = [v for v in CATALOGUE if v.tier == 4]
        unreadable = [v for v in tier_four if v.expected_overall == "unreadable"]
        assert len(unreadable) == 6

    def test_every_verdict_state_appears_in_the_corpus(self) -> None:
        seen = {v.expected_overall for v in curated()}
        assert {"pass", "needs_review", "fail", "unreadable"} <= seen


class TestScoring:
    def test_labels_the_engine_cannot_yet_check_are_excluded_from_the_score(self) -> None:
        # Wine and malt rule sets are Phase 4. Scoring them now would measure
        # an absence rather than an error.
        for variant in curated():
            if variant.beverage_type != "spirits":
                assert not variant.scored, variant.label_id

    def test_an_excluded_label_says_why(self) -> None:
        for variant in CATALOGUE:
            if not variant.scored:
                assert variant.excluded_reason, variant.label_id

    @pytest.mark.parametrize("label_id", ["t2-warning-not-bold", "t2-warning-low-contrast"])
    def test_geometric_violations_are_flagged_as_needing_measurements(self, label_id: str) -> None:
        # Without stroke weight and contrast from the image, these can only be
        # NEEDS_REVIEW. The flag is what stops that from looking like an
        # accuracy failure when it is a missing measurement.
        variant = next(v for v in CATALOGUE if v.label_id == label_id)
        assert variant.requires_layout
