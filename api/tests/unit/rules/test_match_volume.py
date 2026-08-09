"""Net contents matching — docs/specs/rule-engine.md §3.2.

27 CFR 5.70 lets the same bottle be printed several ways: "liter" may be spelled
"litre" or abbreviated "L", "milliliters" may be "ml.", "mL." or "ML.", and U.S.
customary equivalents may appear alongside the metric statement. All of those are
the same volume, and none of them is a discrepancy.
"""

from __future__ import annotations

import pytest

from app.rules.match_volume import UnitSystem, match_volume, parse_net_contents
from app.rules.types import Verdict

FIELD = "net_contents"


class TestParsing:
    @pytest.mark.parametrize(
        ("text", "millilitres"),
        [
            ("750 mL", 750.0),
            ("750ml", 750.0),
            ("750 ML.", 750.0),
            ("750 milliliters", 750.0),
            ("750 millilitres", 750.0),
            ("75 cL", 750.0),
            ("75 centiliters", 750.0),
            ("0.75 L", 750.0),
            ("0.75 litre", 750.0),
            ("1 liter", 1000.0),
            ("1.75 L", 1750.0),
            ("50 mL", 50.0),
        ],
    )
    def test_metric_units_normalise_to_millilitres(self, text: str, millilitres: float) -> None:
        parsed = parse_net_contents(text)
        assert parsed.millilitres == pytest.approx(millilitres)
        assert parsed.system is UnitSystem.METRIC

    @pytest.mark.parametrize(
        ("text", "millilitres"),
        [
            ("25.4 fl oz", 751.17),
            ("1 pint", 473.176473),
            ("1 quart", 946.352946),
            ("1 gallon", 3785.411784),
        ],
    )
    def test_us_customary_units_normalise_to_millilitres(
        self, text: str, millilitres: float
    ) -> None:
        parsed = parse_net_contents(text)
        assert parsed.millilitres == pytest.approx(millilitres, rel=1e-4)
        assert parsed.system is UnitSystem.CUSTOMARY

    def test_the_metric_statement_wins_when_both_are_printed(self) -> None:
        # 27 CFR 5.70 permits the customary equivalent alongside the metric
        # statement. The metric one is the mandatory declaration.
        parsed = parse_net_contents("750 mL (25.4 fl oz)")
        assert parsed.millilitres == pytest.approx(750.0)
        assert parsed.system is UnitSystem.METRIC

    def test_a_number_with_no_unit_does_not_parse(self) -> None:
        parsed = parse_net_contents("750")
        assert parsed.millilitres is None

    def test_empty_text_does_not_parse(self) -> None:
        assert parse_net_contents(None).millilitres is None


class TestMatching:
    def test_identical_statements_pass(self) -> None:
        result = match_volume(FIELD, declared="750 mL", detected="750 mL")
        assert result.verdict is Verdict.PASS

    @pytest.mark.parametrize("detected", ["75 cL", "0.75 L", "750ML.", "750 millilitres"])
    def test_the_same_volume_in_other_units_passes(self, detected: str) -> None:
        result = match_volume(FIELD, declared="750 mL", detected=detected)
        assert result.verdict is Verdict.PASS

    def test_a_unit_difference_is_explained_rather_than_flagged(self) -> None:
        result = match_volume(FIELD, declared="750 mL", detected="75 cL")
        assert "750" in result.reason

    def test_a_different_volume_fails_and_names_both(self) -> None:
        result = match_volume(FIELD, declared="750 mL", detected="700 mL")
        assert result.verdict is Verdict.FAIL
        assert "750" in result.reason
        assert "700" in result.reason

    def test_a_rounded_customary_equivalent_passes(self) -> None:
        # 25.4 fl oz is 751.17 mL: the same bottle, rounded for print.
        result = match_volume(FIELD, declared="750 mL", detected="25.4 fl oz")
        assert result.verdict is Verdict.PASS

    def test_a_genuinely_different_customary_volume_fails(self) -> None:
        # 26 fl oz is 768.9 mL — 2.5% out, past any rounding explanation.
        result = match_volume(FIELD, declared="750 mL", detected="26 fl oz")
        assert result.verdict is Verdict.FAIL


class TestMissingValues:
    def test_declared_but_absent_from_the_label_fails(self) -> None:
        result = match_volume(FIELD, declared="750 mL", detected=None)
        assert result.verdict is Verdict.FAIL
        assert "not found" in result.reason.lower()

    def test_on_the_label_but_not_declared_is_reviewed(self) -> None:
        result = match_volume(FIELD, declared=None, detected="750 mL")
        assert result.verdict is Verdict.NEEDS_REVIEW

    def test_absent_from_both_is_reviewed(self) -> None:
        result = match_volume(FIELD, declared=None, detected=None)
        assert result.verdict is Verdict.NEEDS_REVIEW

    def test_a_missing_unit_is_reviewed_and_quotes_what_it_saw(self) -> None:
        result = match_volume(FIELD, declared="750 mL", detected="750")
        assert result.verdict is Verdict.NEEDS_REVIEW
        assert "750" in result.reason


class TestResultShape:
    def test_declared_and_detected_are_echoed_verbatim(self) -> None:
        result = match_volume(FIELD, declared="750 mL", detected="700 mL")
        assert result.field == FIELD
        assert result.declared == "750 mL"
        assert result.detected == "700 mL"

    def test_every_outcome_carries_a_sentence(self) -> None:
        for declared, detected in [
            ("750 mL", "750 mL"),
            ("750 mL", "700 mL"),
            ("750 mL", "750"),
            ("750 mL", None),
            (None, "750 mL"),
            (None, None),
        ]:
            result = match_volume(FIELD, declared=declared, detected=detected)
            assert result.reason.strip().endswith(".")
            assert len(result.reason) > 20
