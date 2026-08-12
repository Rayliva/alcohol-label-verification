"""27 CFR 5.63 asks whether three fields share one field of vision.

Two ways that went wrong. When two of the three were absent, the survivor set
had one member, every member trivially agreed, and the check emitted PASS
saying "brand name, class or type, and alcohol content all appear on the same
side" — asserting the presence of two fields that were not on the label.

And which side a field was on came from the image's aspect ratio. The same OCR
blocks and the same text passed at 1000x1400 and failed at 1400x800, with a
regulatory citation invented by the frame. A photograph does not say how many
panels a bottle has.
"""

from __future__ import annotations

import pytest

from app.rules.types import LayoutMetrics, Verdict, WarningCheckName
from app.rules.warning import check_warning

WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)


def field_of_vision(sides: dict[str, str]) -> tuple[Verdict, str]:
    report = check_warning(
        detected=WARNING,
        layout=LayoutMetrics(field_sides=sides),
        check_field_of_vision=True,
    )
    check = next(c for c in report.checks if c.check is WarningCheckName.FIELD_OF_VISION)
    return check.verdict, check.reason


class TestItDoesNotVouchForFieldsThatAreNotThere:
    @pytest.mark.parametrize(
        "sides",
        [
            {"brand_name": "front", "class_type": "absent", "alcohol_content": "absent"},
            {"brand_name": "absent", "class_type": "front", "alcohol_content": "absent"},
        ],
    )
    def test_one_survivor_is_not_three_fields_agreeing(self, sides: dict[str, str]) -> None:
        verdict, reason = field_of_vision(sides)
        assert verdict is not Verdict.PASS
        assert "all appear on the same side" not in reason

    def test_two_present_and_together_still_passes(self) -> None:
        verdict, _ = field_of_vision(
            {"brand_name": "front", "class_type": "front", "alcohol_content": "absent"}
        )
        assert verdict is Verdict.PASS

    def test_all_three_present_and_together_passes(self) -> None:
        verdict, reason = field_of_vision(
            {"brand_name": "front", "class_type": "front", "alcohol_content": "front"}
        )
        assert verdict is Verdict.PASS
        assert "all appear on the same side" in reason

    def test_a_genuine_split_reaches_a_person(self) -> None:
        # Not FAIL: which side a field sits on is inferred from the image's
        # aspect ratio, which cannot separate two-panel artwork from a
        # landscape single-panel export. The split still reaches an agent,
        # carrying where each field was seen.
        verdict, reason = field_of_vision(
            {"brand_name": "front", "class_type": "front", "alcohol_content": "back"}
        )
        assert verdict is Verdict.NEEDS_REVIEW
        assert "one panel or two" in reason


class TestAnUnknownSideIsNotAVerdict:
    def test_sides_that_could_not_be_established_ask_for_a_person(self) -> None:
        # A wide photograph might be two panels or one panel of a wide label.
        # Guessing produced a confident citation either way.
        verdict, _ = field_of_vision({"brand_name": "front"})
        assert verdict is Verdict.NEEDS_REVIEW
