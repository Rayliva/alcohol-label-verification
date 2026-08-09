"""The rule engine — docs/specs/rule-engine.md §3.4, §3.5.

Two things are under test. That the engine folds field results into one label
outcome correctly, and that beverage types are *configuration* rather than code
paths — a hardcoded spirits engine would emit false violations on two of the
three categories the brief names.
"""

from __future__ import annotations

import pytest

from app.rules.beverage_types import (
    BeverageTypeUnavailableError,
    available_beverage_types,
    rules_for,
)
from app.rules.engine import Application, LabelObservation, evaluate
from app.rules.types import LayoutMetrics, Verdict, WarningCheckName
from app.rules.warning import STATUTORY_WARNING

GOOD_LAYOUT = LayoutMetrics(
    warning_text_height=11.0,
    median_text_height=12.0,
    warning_prefix_stroke_ratio=1.4,
    warning_contrast_ratio=17.0,
    field_sides={"brand_name": "front", "class_type": "front", "alcohol_content": "front"},
)

DECLARED = {
    "brand_name": "OLD TOM DISTILLERY",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45% Alc./Vol. (90 Proof)",
    "net_contents": "750 mL",
    "bottler_address": "Bottled by Old Tom Distillery, Bardstown, Kentucky",
}


def spirits_application(**overrides: str | None) -> Application:
    return Application(beverage_type="spirits", fields={**DECLARED, **overrides})


def spirits_label(**overrides: str | None) -> LabelObservation:
    detected = {**DECLARED, "government_warning": STATUTORY_WARNING}
    return LabelObservation(fields={**detected, **overrides}, layout=GOOD_LAYOUT)


class TestCompliantLabel:
    def test_a_matching_label_passes(self) -> None:
        report = evaluate(spirits_application(), spirits_label())
        assert report.overall is Verdict.PASS

    def test_every_required_field_is_reported(self) -> None:
        report = evaluate(spirits_application(), spirits_label())
        reported = [result.field for result in report.fields]
        assert reported == [
            "brand_name",
            "class_type",
            "alcohol_content",
            "net_contents",
            "bottler_address",
            "government_warning",
        ]

    def test_fields_are_reported_in_configuration_order(self) -> None:
        report = evaluate(spirits_application(), spirits_label())
        configured = [
            rule.field
            for rule in rules_for("spirits").fields
            if rule.field in {r.field for r in report.fields}
        ]
        assert [r.field for r in report.fields] == configured

    def test_the_warning_sub_checks_come_back_with_the_report(self) -> None:
        report = evaluate(spirits_application(), spirits_label())
        assert len(report.warning_checks) == 6
        assert WarningCheckName.FIELD_OF_VISION in {c.check for c in report.warning_checks}


class TestOverallOutcome:
    def test_one_failing_field_fails_the_label(self) -> None:
        report = evaluate(spirits_application(), spirits_label(net_contents="700 mL"))
        assert report.overall is Verdict.FAIL

    def test_one_uncertain_field_needs_review(self) -> None:
        report = evaluate(spirits_application(), spirits_label(alcohol_content="45.2% Alc./Vol."))
        assert report.overall is Verdict.NEEDS_REVIEW

    def test_a_failure_outranks_an_uncertainty(self) -> None:
        report = evaluate(
            spirits_application(),
            spirits_label(net_contents="700 mL", alcohol_content="45.2% Alc./Vol."),
        )
        assert report.overall is Verdict.FAIL

    def test_a_warning_violation_fails_the_label(self) -> None:
        title_case = STATUTORY_WARNING.replace("GOVERNMENT WARNING", "Government Warning")
        report = evaluate(spirits_application(), spirits_label(government_warning=title_case))
        assert report.overall is Verdict.FAIL

    def test_the_counts_match_the_field_results(self) -> None:
        report = evaluate(spirits_application(), spirits_label(net_contents="700 mL"))
        assert report.counts[Verdict.FAIL] == 1
        assert report.counts[Verdict.PASS] == len(report.fields) - 1


class TestMatcherDispatch:
    def test_alcohol_content_goes_through_the_numeric_matcher(self) -> None:
        # Text matching would call this a formatting difference at best; the
        # numeric matcher reads both statements as 45% and 90 proof.
        report = evaluate(
            spirits_application(), spirits_label(alcohol_content="45% ALC/VOL (90 PROOF)")
        )
        result = next(r for r in report.fields if r.field == "alcohol_content")
        assert result.verdict is Verdict.PASS

    def test_net_contents_goes_through_the_volume_matcher(self) -> None:
        report = evaluate(spirits_application(), spirits_label(net_contents="75 cL"))
        result = next(r for r in report.fields if r.field == "net_contents")
        assert result.verdict is Verdict.PASS

    def test_brand_name_goes_through_the_fuzzy_text_matcher(self) -> None:
        # Dave Morrison's example: obviously the same thing.
        report = evaluate(
            spirits_application(brand_name="Stone's Throw"),
            spirits_label(brand_name="STONE'S THROW"),
        )
        result = next(r for r in report.fields if r.field == "brand_name")
        assert result.verdict is Verdict.PASS


class TestConditionalFields:
    def test_country_of_origin_is_skipped_when_neither_side_mentions_it(self) -> None:
        # It is required for imports only. Reporting it on a domestic bourbon
        # would be a false violation on every label in the country.
        report = evaluate(spirits_application(), spirits_label())
        assert "country_of_origin" not in {r.field for r in report.fields}

    def test_country_of_origin_is_checked_once_it_is_declared(self) -> None:
        report = evaluate(
            spirits_application(country_of_origin="Scotland"),
            spirits_label(country_of_origin="Product of Scotland"),
        )
        assert "country_of_origin" in {r.field for r in report.fields}

    def test_a_country_on_the_label_but_not_the_form_is_still_checked(self) -> None:
        report = evaluate(
            spirits_application(),
            spirits_label(country_of_origin="Product of Scotland"),
        )
        result = next(r for r in report.fields if r.field == "country_of_origin")
        assert result.verdict is Verdict.NEEDS_REVIEW


class TestBeverageTypesAreConfiguration:
    def test_all_three_types_are_registered(self) -> None:
        # Wine and malt exist as configuration from the first commit. Their
        # content is Phase 4; retrofitting the shape later would be the
        # expensive version of this decision.
        assert {t.beverage_type for t in available_beverage_types()} == {
            "spirits",
            "wine",
            "malt",
        }

    def test_only_spirits_is_available_in_phase_one(self) -> None:
        assert rules_for("spirits").available is True
        assert rules_for("wine").available is False
        assert rules_for("malt").available is False

    def test_an_unavailable_type_explains_itself_rather_than_returning_verdicts(self) -> None:
        with pytest.raises(BeverageTypeUnavailableError) as raised:
            evaluate(
                Application(beverage_type="wine", fields=DECLARED),
                LabelObservation(fields={}, layout=None),
            )
        assert "wine" in str(raised.value).lower()

    def test_an_unknown_type_fails_loudly(self) -> None:
        with pytest.raises(KeyError):
            rules_for("mead")

    def test_wine_alcohol_content_is_conditional_not_required(self) -> None:
        # 27 CFR 4.36 lets wine at 14% or less omit the percentage when the
        # label says "table wine". Requiring it would reject a valid label.
        wine = rules_for("wine")
        rule = next(r for r in wine.fields if r.field == "alcohol_content")
        assert rule.requirement is not rule.requirement.REQUIRED

    def test_malt_alcohol_content_is_conditional_not_required(self) -> None:
        # 27 CFR 7.63 requires it only when alcohol comes from added
        # nonbeverage ingredients.
        malt = rules_for("malt")
        rule = next(r for r in malt.fields if r.field == "alcohol_content")
        assert rule.requirement is not rule.requirement.REQUIRED

    def test_field_of_vision_governs_spirits_only(self) -> None:
        # 27 CFR 5.63 is a distilled spirits section.
        assert rules_for("spirits").checks_field_of_vision is True
        assert rules_for("wine").checks_field_of_vision is False
        assert rules_for("malt").checks_field_of_vision is False

    def test_every_field_rule_cites_its_regulation(self) -> None:
        for beverage in available_beverage_types():
            for rule in beverage.fields:
                assert "CFR" in rule.citation


class TestMissingFields:
    def test_a_field_missing_from_the_label_fails(self) -> None:
        report = evaluate(spirits_application(), spirits_label(net_contents=None))
        result = next(r for r in report.fields if r.field == "net_contents")
        assert result.verdict is Verdict.FAIL

    def test_a_label_with_no_warning_fails(self) -> None:
        report = evaluate(spirits_application(), spirits_label(government_warning=None))
        assert report.overall is Verdict.FAIL
        assert all(c.verdict is Verdict.FAIL for c in report.warning_checks)

    def test_no_layout_data_never_produces_a_pass_on_a_geometric_check(self) -> None:
        observation = LabelObservation(fields=spirits_label().fields, layout=None)
        report = evaluate(spirits_application(), observation)
        geometric = {
            WarningCheckName.BOLD,
            WarningCheckName.PROPORTION,
            WarningCheckName.CONTRAST,
            WarningCheckName.FIELD_OF_VISION,
        }
        for check in report.warning_checks:
            if check.check in geometric:
                assert check.verdict is Verdict.NEEDS_REVIEW
