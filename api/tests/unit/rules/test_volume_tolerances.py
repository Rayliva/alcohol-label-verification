"""Two volumes printed in the same system must be the same number.

The same-system tolerance was relative (0.1%), described in the code as float
slack. It is not: on a 1 L bottle it permits a whole millilitre, and it scales
with the bottle. A label printing 1001 mL against a declared 1000 mL came back
PASS with a reason asserting the two were the same volume.

Across systems a real allowance is right, because the label is a rounded
conversion of the same bottle — but it has to be wide enough for the customary
forms that actually appear, which the module's own docstring names.
"""

from __future__ import annotations

import pytest

from app.rules.match_volume import match_volume
from app.rules.types import Verdict


def verdict(declared: str, detected: str) -> Verdict:
    return match_volume("net_contents", declared=declared, detected=detected).verdict


class TestTheSameSystemMeansTheSameNumber:
    @pytest.mark.parametrize(
        ("declared", "detected"),
        [
            ("1000 mL", "1001 mL"),
            ("1 L", "1001 mL"),
            ("750 mL", "751 mL"),
            ("1.75 L", "1752 mL"),
        ],
    )
    def test_a_different_printed_number_does_not_pass(self, declared: str, detected: str) -> None:
        assert verdict(declared, detected) is not Verdict.PASS

    @pytest.mark.parametrize(
        ("declared", "detected"),
        [
            ("750 mL", "750 mL"),
            ("1 L", "1000 mL"),
            ("1.75 L", "1750 mL"),
            ("75 cl", "750 mL"),
        ],
    )
    def test_the_same_volume_written_differently_still_passes(
        self, declared: str, detected: str
    ) -> None:
        assert verdict(declared, detected) is Verdict.PASS


class TestCustomaryFormsAreNotAccusations:
    def test_a_pint_and_ounces_matches_the_metric_it_converts_from(self) -> None:
        # 1 PT 9 FL OZ is 739.34 mL against a declared 750 mL — 1.4% apart, so
        # a 1% allowance failed it. The module's own docstring names this as a
        # real net contents form.
        assert verdict("750 mL", "1 PT 9 FL OZ") is not Verdict.FAIL

    def test_a_rounded_ounce_conversion_still_passes(self) -> None:
        assert verdict("750 mL", "25.4 fl oz") is Verdict.PASS

    def test_a_genuinely_different_bottle_still_fails(self) -> None:
        # 700 mL against 750 mL is 6.7% — a different bottle, not a rounding.
        assert verdict("750 mL", "23.7 fl oz") is Verdict.FAIL


class TestOneVolumeWrittenTwiceIsNotTwoVolumes:
    @pytest.mark.parametrize(
        "detected",
        ["70 cl 700 ml", "1.75 L (1750 mL)", "750 mL / 75 cl"],
    )
    def test_the_same_quantity_restated_is_not_summed(self, detected: str) -> None:
        # Summing is right for "1 L 500 mL". It is wrong when one volume is
        # printed in two spellings, which is ordinary on imported spirits.
        declared = (
            "1.75 L"
            if detected.startswith("1.75")
            else "700 mL"
            if detected.startswith("70 cl")
            else "750 mL"
        )
        assert verdict(declared, detected) is not Verdict.FAIL

    def test_genuinely_additive_contents_still_sum(self) -> None:
        assert verdict("1500 mL", "1 L 500 mL") is Verdict.PASS
