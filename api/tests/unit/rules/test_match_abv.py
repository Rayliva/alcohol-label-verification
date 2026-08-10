"""Alcohol content matching — docs/specs/rule-engine.md §3.1.

Two things are being checked at once and they are different questions:

  1. Does the label agree with itself?   (proof == 2 x ABV, 27 CFR 5.1)
  2. Does the label agree with the form? (documents should agree exactly)

The regulatory +/-0.3 tolerance answers neither. It governs the labelled figure
against the liquid in the bottle, so it never appears here as a pass rule.
"""

from __future__ import annotations

import pytest

from app.rules.match_abv import match_abv, parse_alcohol_content
from app.rules.types import Verdict

FIELD = "alcohol_content"


class TestParsing:
    @pytest.mark.parametrize(
        ("text", "abv", "proof"),
        [
            ("45% Alc./Vol. (90 Proof)", 45.0, 90.0),
            ("ALC. 45% BY VOL.", 45.0, None),
            ("Alcohol 45 percent by volume", 45.0, None),
            ("40% alc/vol", 40.0, None),
            ("45.5% Alc/Vol", 45.5, None),
            ("90 Proof", None, 90.0),
            ("Alcohol by volume 45%", 45.0, None),
            ("45.0% ALC/VOL (90 PROOF)", 45.0, 90.0),
            ("90°", None, 90.0),
        ],
    )
    def test_recovers_abv_and_proof(
        self, text: str, abv: float | None, proof: float | None
    ) -> None:
        parsed = parse_alcohol_content(text)
        assert parsed.abv == abv
        assert parsed.proof == proof

    def test_a_bare_number_does_not_parse(self) -> None:
        # Guessing whether a stray "45" meant percent or proof is the
        # confident-and-wrong failure this product cannot afford.
        parsed = parse_alcohol_content("45")
        assert parsed.abv is None
        assert parsed.proof is None

    def test_empty_text_does_not_parse(self) -> None:
        parsed = parse_alcohol_content(None)
        assert parsed.abv is None
        assert parsed.proof is None


class TestMatchingValues:
    def test_same_value_different_formatting_passes(self) -> None:
        result = match_abv(
            FIELD,
            declared="45% Alc./Vol. (90 Proof)",
            detected="45% ALC/VOL (90 PROOF)",
        )
        assert result.verdict is Verdict.PASS

    def test_trailing_zeros_are_the_same_number(self) -> None:
        result = match_abv(FIELD, declared="45%", detected="45.00% ALC/VOL")
        assert result.verdict is Verdict.PASS

    def test_a_clearly_different_abv_fails(self) -> None:
        result = match_abv(FIELD, declared="45% Alc./Vol.", detected="40% Alc./Vol.")
        assert result.verdict is Verdict.FAIL
        assert "45" in result.reason
        assert "40" in result.reason

    def test_a_small_difference_is_reviewed_not_passed(self) -> None:
        result = match_abv(FIELD, declared="45%", detected="45.2%")
        assert result.verdict is Verdict.NEEDS_REVIEW

    def test_a_small_difference_explains_that_the_tolerance_does_not_apply(self) -> None:
        # An agent who knows 27 CFR 5.65 will ask why 0.2 points was flagged.
        # The reason has to answer that before they dismiss the tool.
        result = match_abv(FIELD, declared="45%", detected="45.2%")
        assert "0.3" in result.reason
        assert "liquid" in result.reason.lower()


class TestLabelInternalConsistency:
    def test_proof_that_is_not_twice_the_abv_fails(self) -> None:
        result = match_abv(
            FIELD,
            declared="45% Alc./Vol. (90 Proof)",
            detected="45% Alc./Vol. (80 Proof)",
        )
        assert result.verdict is Verdict.FAIL
        assert "80" in result.reason
        assert "45" in result.reason

    def test_internal_contradiction_is_reported_even_when_the_abv_matches(self) -> None:
        # The label contradicts itself. That is a defect in the label whatever
        # the application says, so it outranks the form comparison.
        result = match_abv(FIELD, declared="45%", detected="45% Alc./Vol. (100 Proof)")
        assert result.verdict is Verdict.FAIL
        assert "twice" in result.reason.lower()

    def test_proof_only_on_the_label_fails_because_percent_is_mandatory(self) -> None:
        # 27 CFR 5.65: alcohol content "must be stated on the label as a
        # percentage of alcohol by volume".
        result = match_abv(FIELD, declared="45% Alc./Vol. (90 Proof)", detected="90 Proof")
        assert result.verdict is Verdict.FAIL
        assert "percentage" in result.reason.lower()

    def test_a_proof_difference_alone_is_reviewed(self) -> None:
        # Both statements are internally consistent, but the form and the label
        # disagree on a figure the label is allowed to print.
        result = match_abv(FIELD, declared="45% Alc./Vol. (90 Proof)", detected="45% Alc./Vol.")
        assert result.verdict is Verdict.NEEDS_REVIEW


class TestMissingValues:
    def test_declared_but_absent_from_the_label_fails(self) -> None:
        result = match_abv(FIELD, declared="45% Alc./Vol.", detected=None)
        assert result.verdict is Verdict.FAIL
        assert "not found" in result.reason.lower()

    def test_on_the_label_but_not_declared_is_reviewed(self) -> None:
        result = match_abv(FIELD, declared=None, detected="45% Alc./Vol.")
        assert result.verdict is Verdict.NEEDS_REVIEW

    def test_absent_from_both_is_reviewed(self) -> None:
        result = match_abv(FIELD, declared=None, detected=None)
        assert result.verdict is Verdict.NEEDS_REVIEW

    def test_unparseable_label_text_is_reviewed_and_quotes_what_it_saw(self) -> None:
        result = match_abv(FIELD, declared="45% Alc./Vol.", detected="ALC. BY VOL.")
        assert result.verdict is Verdict.NEEDS_REVIEW
        assert "ALC. BY VOL." in result.reason


class TestResultShape:
    def test_declared_and_detected_are_echoed_verbatim(self) -> None:
        result = match_abv(FIELD, declared="45% Alc./Vol.", detected="40% Alc./Vol.")
        assert result.field == FIELD
        assert result.declared == "45% Alc./Vol."
        assert result.detected == "40% Alc./Vol."

    def test_every_outcome_carries_a_sentence(self) -> None:
        for declared, detected in [
            ("45%", "45%"),
            ("45%", "40%"),
            ("45%", "45.2%"),
            ("45%", None),
            (None, "45%"),
            (None, None),
        ]:
            result = match_abv(FIELD, declared=declared, detected=detected)
            assert result.reason.strip().endswith(".")
            assert len(result.reason) > 20


class TestNumbersThatMustNotParse:
    """Regressions from the pre-push review, 2026-08-09.

    Every one of these produced a false PASS: the regex had no left boundary,
    so it matched the tail of a grouped number and reported a 45.5% spirit as
    a 5% one. A false PASS on alcohol content is the error class this product
    exists to prevent.
    """

    def test_a_comma_grouped_number_does_not_parse_from_its_tail(self) -> None:
        parsed = parse_alcohol_content("45,5% Alc/Vol")
        assert parsed.abv is None

    def test_a_comma_decimal_is_not_read_as_a_smaller_number(self) -> None:
        result = match_abv(FIELD, declared="5% Alc/Vol", detected="45,5% Alc/Vol")
        assert result.verdict is not Verdict.PASS

    def test_a_proof_with_a_grouped_number_does_not_parse(self) -> None:
        assert parse_alcohol_content("1,090 Proof").proof is None

    def test_two_different_percentages_are_ambiguous_rather_than_guessed(self) -> None:
        # "40% grain neutral spirits" is not the alcohol content statement.
        parsed = parse_alcohol_content("contains 40% grain neutral spirits, 20% alc/vol")
        assert parsed.abv is None

    def test_the_same_percentage_repeated_still_parses(self) -> None:
        parsed = parse_alcohol_content("45% Alc./Vol. — 45% ABV")
        assert parsed.abv == 45.0

    def test_an_ambiguous_statement_is_reviewed_not_passed(self) -> None:
        result = match_abv(
            FIELD,
            declared="40% Alc/Vol",
            detected="contains 40% grain neutral spirits, 20% alc/vol",
        )
        assert result.verdict is Verdict.NEEDS_REVIEW
