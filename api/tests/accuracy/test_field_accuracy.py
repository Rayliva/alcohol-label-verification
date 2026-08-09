"""Field-verdict accuracy against the curated corpus — PRD → Goals & metrics.

Two targets, and they are not symmetric:

  * >= 95% field-verdict accuracy
  * **zero** false PASS on a government warning violation

A false FAIL costs an agent ten seconds. A false PASS lets non-compliant product
reach market, so it is the error this suite refuses outright.

**What this measures, precisely.** OCR and extraction are held perfect: OCR
replays the boxes the renderer drew, and the declared-vs-detected comparison
uses what the artwork actually says. So this number is the accuracy of the rule
engine and the geometry measurements *in isolation*. It is not an end-to-end
number, and the README says so rather than letting the flattering figure stand
for the product. Labels this suite cannot score are counted and named at the end
of the run — a silent exclusion would read as coverage we do not have.
"""

from __future__ import annotations

import pytest

from app.errors import UnreadableImageError
from app.pipeline import verify
from app.rules.types import Verdict
from tests.support import corpus

pytestmark = pytest.mark.accuracy

TARGET_ACCURACY = 0.95


@pytest.fixture(scope="module")
def scored() -> list[corpus.CorpusLabel]:
    """Every label the engine can be held to today."""
    return [
        label for label in corpus.load() if label.variant.scored and not label.variant.degradation
    ]


@pytest.fixture(scope="module")
def ocr() -> corpus.CorpusOcrEngine:
    return corpus.CorpusOcrEngine()


def _verdicts(label: corpus.CorpusLabel, ocr: corpus.CorpusOcrEngine) -> dict[str, str]:
    result = verify(label.image_bytes, label.application, ocr=ocr, extract=lambda _: label.detected)
    return {field.field: field.verdict.value for field in result.report.fields}


def test_field_verdict_accuracy_meets_the_target(scored, ocr, capsys) -> None:
    wrong: list[str] = []
    total = 0

    for label in scored:
        actual = _verdicts(label, ocr)
        for field, expected in label.variant.expected_fields.items():
            if field not in actual:
                continue  # a conditional field the engine correctly skipped
            total += 1
            if actual[field] != expected:
                wrong.append(f"{label.label_id}.{field}: expected {expected}, got {actual[field]}")

    accuracy = (total - len(wrong)) / total if total else 0.0
    with capsys.disabled():
        print(f"\nField verdicts scored: {total}")
        print(f"Accuracy: {accuracy:.1%} (target {TARGET_ACCURACY:.0%})")
        for line in wrong:
            print(f"  wrong: {line}")

    assert total >= 250, f"only {total} field verdicts scored; the corpus should give ~300"
    assert accuracy >= TARGET_ACCURACY, "\n".join(wrong)


def test_no_warning_violation_is_ever_passed(scored, ocr) -> None:
    escaped = []
    for label in scored:
        expected = label.variant.expected_fields.get("government_warning")
        if expected != "fail":
            continue
        actual = _verdicts(label, ocr).get("government_warning")
        if actual == Verdict.PASS.value:
            escaped.append(label.label_id)
    assert not escaped, f"government warning violations reported as PASS: {escaped}"


def test_overall_outcomes_match(scored, ocr) -> None:
    wrong = []
    for label in scored:
        result = verify(
            label.image_bytes,
            label.application,
            ocr=ocr,
            extract=lambda _, detected=label.detected: detected,
        )
        if result.report.overall.value != label.variant.expected_overall:
            wrong.append(
                f"{label.label_id}: expected {label.variant.expected_overall}, "
                f"got {result.report.overall.value}"
            )
    assert not wrong, "\n".join(wrong)


def test_unreadable_labels_are_reported_as_unreadable(ocr) -> None:
    """The other half of tier 4: they must fail, and name why."""
    unreadable = [
        label for label in corpus.load(tiers=(4,)) if label.variant.expected_overall == "unreadable"
    ]
    assert unreadable, "tier 4 should carry six unreadable labels"

    survived = []
    for label in unreadable:
        try:
            verify(
                label.image_bytes,
                label.application,
                ocr=ocr,
                extract=lambda _, detected=label.detected: detected,
            )
            survived.append(label.label_id)
        except UnreadableImageError as exc:
            assert exc.code, label.label_id
            assert exc.what_to_do, label.label_id
        except corpus.CorpusMissingError:
            # Reached OCR, which means the image passed the quality gate.
            survived.append(label.label_id)
    assert not survived, f"unreadable labels that produced verdicts anyway: {survived}"


def test_what_this_suite_does_not_cover_is_stated(capsys) -> None:
    """Name the exclusions rather than letting the number imply full coverage."""
    everything = corpus.load()
    excluded = [label for label in everything if not label.variant.scored]
    degraded = [label for label in everything if label.variant.scored and label.variant.degradation]
    reasons = sorted({label.variant.excluded_reason for label in excluded})
    with capsys.disabled():
        print(f"\nNot scored ({len(excluded)}): {'; '.join(reasons)}")
        print(
            f"Readable-but-degraded labels excluded offline ({len(degraded)}): "
            "they carry no ground-truth OCR by design — OCR is the thing under "
            "stress there, so they need a live engine."
        )
    assert excluded or degraded
