"""A verdict is only as good as the reading behind it.

OCR reports how sure it was about each piece of text. Until now that was
averaged into one number, used for a single go/no-go gate, and discarded — so
a field whose evidence was barely legible produced a verdict stated with the
same confidence as one read cleanly.

That is the difference between "this label is wrong" and "we could not read
this label", and an agent needs to be told which one they are looking at.
Measured on the sample set: clean labels never read a block below 0.94, while
the degraded ones carry blocks at 0.54 and 0.61.
"""

from __future__ import annotations

from app.ocr.base import BoundingBox, OcrResult, TextBlock
from app.pipeline.run import temper_by_reading
from app.rules.types import FieldResult, Verdict


def block(text: str, confidence: float) -> TextBlock:
    return TextBlock(
        text=text, box=BoundingBox(x=0, y=0, width=100, height=20), confidence=confidence
    )


def ocr_of(*blocks: TextBlock) -> OcrResult:
    return OcrResult(
        full_text="\n".join(b.text for b in blocks),
        blocks=blocks,
        image_width=1000,
        image_height=1400,
        engine="test",
        latency_ms=0.0,
    )


def result(field: str, detected: str | None, verdict: Verdict) -> FieldResult:
    return FieldResult(
        field=field,
        declared="OLD TOM DISTILLERY",
        detected=detected,
        verdict=verdict,
        confidence=1.0,
        reason="Reason from the matcher.",
    )


class TestAPoorlyReadFieldIsNotADecidedOne:
    def test_a_fail_on_barely_legible_text_becomes_a_review(self) -> None:
        ocr = ocr_of(block("0LD T0M D1STILLERY", 0.55))
        [tempered] = temper_by_reading(
            [result("brand_name", "0LD T0M D1STILLERY", Verdict.FAIL)], ocr
        )
        assert tempered.verdict is Verdict.NEEDS_REVIEW

    def test_and_the_reason_says_it_was_the_reading(self) -> None:
        ocr = ocr_of(block("0LD T0M D1STILLERY", 0.55))
        [tempered] = temper_by_reading(
            [result("brand_name", "0LD T0M D1STILLERY", Verdict.FAIL)], ocr
        )
        assert "could not be read" in tempered.reason.lower()
        # The original finding is not thrown away — the agent still sees what
        # the matcher thought, so they can judge both at once.
        assert "Reason from the matcher." in tempered.reason

    def test_a_pass_on_barely_legible_text_becomes_a_review_too(self) -> None:
        # A confident PASS built on a guess is a false PASS, which is the
        # error class this tool can least afford.
        ocr = ocr_of(block("OLD TOM DISTILLERY", 0.55))
        [tempered] = temper_by_reading(
            [result("brand_name", "OLD TOM DISTILLERY", Verdict.PASS)], ocr
        )
        assert tempered.verdict is Verdict.NEEDS_REVIEW


class TestCleanReadingIsLeftAlone:
    def test_a_confident_fail_stays_a_fail(self) -> None:
        ocr = ocr_of(block("SOMETHING ELSE", 0.97))
        [tempered] = temper_by_reading([result("brand_name", "SOMETHING ELSE", Verdict.FAIL)], ocr)
        assert tempered.verdict is Verdict.FAIL
        assert tempered.reason == "Reason from the matcher."

    def test_a_confident_pass_stays_a_pass(self) -> None:
        ocr = ocr_of(block("OLD TOM DISTILLERY", 0.96))
        [tempered] = temper_by_reading(
            [result("brand_name", "OLD TOM DISTILLERY", Verdict.PASS)], ocr
        )
        assert tempered.verdict is Verdict.PASS

    def test_a_field_with_no_text_to_read_is_untouched(self) -> None:
        # Nothing was found, so there is no reading to doubt. Whether an absent
        # field is a violation is the matcher's call, not this one's.
        ocr = ocr_of(block("OLD TOM DISTILLERY", 0.96))
        [tempered] = temper_by_reading([result("net_contents", None, Verdict.FAIL)], ocr)
        assert tempered.verdict is Verdict.FAIL

    def test_an_engine_that_reports_no_confidence_changes_nothing(self) -> None:
        # The fake engine and some providers return none at all. Absence of a
        # signal is not evidence of a bad reading.
        ocr = ocr_of(
            TextBlock(
                text="OLD TOM DISTILLERY",
                box=BoundingBox(x=0, y=0, width=100, height=20),
                confidence=None,
            )
        )
        [tempered] = temper_by_reading(
            [result("brand_name", "OLD TOM DISTILLERY", Verdict.FAIL)], ocr
        )
        assert tempered.verdict is Verdict.FAIL
