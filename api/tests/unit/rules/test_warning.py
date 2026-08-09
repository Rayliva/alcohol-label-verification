"""Government warning checks — docs/specs/rule-engine.md §3.3.

This is the one exact check in the product and the one with the most ways to
fail. A junior agent's account of it: "people try to get creative with the
warning all the time. Smaller font, different wording, burying it in tiny text.
I caught one last month where they used 'Government Warning' in title case
instead of all caps. Rejected."

Every test here exists because a false PASS on this field is the expensive error.
"""

from __future__ import annotations

from app.rules.types import LayoutMetrics, Verdict, WarningCheckName
from app.rules.warning import STATUTORY_WARNING, check_warning

# A label where every measurement is comfortably compliant.
GOOD_LAYOUT = LayoutMetrics(
    warning_text_height=11.0,
    median_text_height=12.0,
    warning_prefix_stroke_ratio=1.4,
    warning_contrast_ratio=17.0,
    field_sides={"brand_name": "front", "class_type": "front", "alcohol_content": "front"},
)


def verdict_for(checks: tuple, name: WarningCheckName) -> Verdict:
    return next(c.verdict for c in checks if c.check is name)


def reason_for(checks: tuple, name: WarningCheckName) -> str:
    return next(c.reason for c in checks if c.check is name)


class TestStatutoryText:
    def test_the_verbatim_warning_passes(self) -> None:
        report = check_warning(detected=STATUTORY_WARNING, layout=GOOD_LAYOUT)
        assert verdict_for(report.checks, WarningCheckName.TEXT_EXACT) is Verdict.PASS
        assert report.field_result.verdict is Verdict.PASS

    def test_line_breaks_are_layout_not_a_violation(self) -> None:
        wrapped = STATUTORY_WARNING.replace("(2)", "\n(2)").replace("General,", "General,\n   ")
        report = check_warning(detected=wrapped, layout=GOOD_LAYOUT)
        assert verdict_for(report.checks, WarningCheckName.TEXT_EXACT) is Verdict.PASS

    def test_one_altered_word_fails_and_names_it(self) -> None:
        altered = STATUTORY_WARNING.replace("birth defects", "birth defect")
        report = check_warning(detected=altered, layout=GOOD_LAYOUT)
        assert verdict_for(report.checks, WarningCheckName.TEXT_EXACT) is Verdict.FAIL
        reason = reason_for(report.checks, WarningCheckName.TEXT_EXACT)
        assert "defects" in reason
        assert "defect." in reason or "defect " in reason or '"defect"' in reason

    def test_a_paraphrase_fails(self) -> None:
        paraphrased = (
            "GOVERNMENT WARNING: (1) The Surgeon General says women should not drink "
            "alcohol while pregnant due to the risk of birth defects. (2) Drinking "
            "alcohol impairs your ability to drive or operate machinery and may cause "
            "health problems."
        )
        report = check_warning(detected=paraphrased, layout=GOOD_LAYOUT)
        assert verdict_for(report.checks, WarningCheckName.TEXT_EXACT) is Verdict.FAIL

    def test_a_dropped_clause_fails(self) -> None:
        truncated = STATUTORY_WARNING.split("(2)")[0].strip()
        report = check_warning(detected=truncated, layout=GOOD_LAYOUT)
        assert verdict_for(report.checks, WarningCheckName.TEXT_EXACT) is Verdict.FAIL


class TestCapitals:
    def test_title_case_prefix_fails(self) -> None:
        # 27 CFR 16.22 requires the prefix in capital letters.
        title_case = STATUTORY_WARNING.replace("GOVERNMENT WARNING", "Government Warning")
        report = check_warning(detected=title_case, layout=GOOD_LAYOUT)
        assert verdict_for(report.checks, WarningCheckName.CAPS) is Verdict.FAIL
        assert "capital letters" in reason_for(report.checks, WarningCheckName.CAPS)

    def test_title_case_prefix_also_fails_the_exact_text_check(self) -> None:
        # Case folding anywhere in this module would hide the violation.
        title_case = STATUTORY_WARNING.replace("GOVERNMENT WARNING", "Government Warning")
        report = check_warning(detected=title_case, layout=GOOD_LAYOUT)
        assert verdict_for(report.checks, WarningCheckName.TEXT_EXACT) is Verdict.FAIL

    def test_capitals_pass_on_the_statutory_text(self) -> None:
        report = check_warning(detected=STATUTORY_WARNING, layout=GOOD_LAYOUT)
        assert verdict_for(report.checks, WarningCheckName.CAPS) is Verdict.PASS


class TestBold:
    def test_a_clearly_bold_prefix_passes(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_prefix_stroke_ratio=1.4)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.BOLD) is Verdict.PASS

    def test_a_marginal_stroke_weight_is_reviewed(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_prefix_stroke_ratio=1.10)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.BOLD) is Verdict.NEEDS_REVIEW

    def test_a_prefix_no_heavier_than_the_body_fails(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_prefix_stroke_ratio=1.0)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.BOLD) is Verdict.FAIL


class TestProportion:
    def test_warning_text_the_size_of_body_text_passes(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_text_height=11.0, median_text_height=12.0)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.PROPORTION) is Verdict.PASS

    def test_somewhat_small_warning_text_is_reviewed(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_text_height=8.4, median_text_height=12.0)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.PROPORTION) is Verdict.NEEDS_REVIEW

    def test_buried_in_tiny_text_fails(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_text_height=4.8, median_text_height=12.0)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.PROPORTION) is Verdict.FAIL
        assert "40%" in reason_for(report.checks, WarningCheckName.PROPORTION)


class TestContrast:
    def test_dark_text_on_a_light_background_passes(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_contrast_ratio=17.0)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.CONTRAST) is Verdict.PASS

    def test_marginal_contrast_is_reviewed(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_contrast_ratio=3.5)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.CONTRAST) is Verdict.NEEDS_REVIEW

    def test_text_that_barely_separates_from_its_background_fails(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_contrast_ratio=1.4)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.CONTRAST) is Verdict.FAIL


class TestFieldOfVision:
    def test_all_three_on_one_side_passes(self) -> None:
        report = check_warning(detected=STATUTORY_WARNING, layout=GOOD_LAYOUT)
        assert verdict_for(report.checks, WarningCheckName.FIELD_OF_VISION) is Verdict.PASS

    def test_alcohol_content_on_the_back_fails(self) -> None:
        # 27 CFR 5.63 requires brand, class/type and alcohol content in the
        # same field of vision.
        layout = GOOD_LAYOUT.replace(
            field_sides={
                "brand_name": "front",
                "class_type": "front",
                "alcohol_content": "back",
            }
        )
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.FIELD_OF_VISION) is Verdict.FAIL

    def test_it_is_omitted_for_beverage_types_it_does_not_govern(self) -> None:
        report = check_warning(
            detected=STATUTORY_WARNING, layout=GOOD_LAYOUT, check_field_of_vision=False
        )
        names = [c.check for c in report.checks]
        assert WarningCheckName.FIELD_OF_VISION not in names
        assert len(report.checks) == 5


class TestMissingMeasurements:
    def test_no_layout_never_passes_a_geometric_check(self) -> None:
        # A check that silently passes when it did not run is a false PASS, and
        # false PASSes are the error class this product is scored on.
        report = check_warning(detected=STATUTORY_WARNING, layout=None)
        for name in (
            WarningCheckName.BOLD,
            WarningCheckName.PROPORTION,
            WarningCheckName.CONTRAST,
            WarningCheckName.FIELD_OF_VISION,
        ):
            assert verdict_for(report.checks, name) is Verdict.NEEDS_REVIEW

    def test_the_text_checks_still_run_without_layout(self) -> None:
        report = check_warning(detected=STATUTORY_WARNING, layout=None)
        assert verdict_for(report.checks, WarningCheckName.TEXT_EXACT) is Verdict.PASS
        assert verdict_for(report.checks, WarningCheckName.CAPS) is Verdict.PASS

    def test_a_missing_stroke_measurement_is_reviewed_not_passed(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_prefix_stroke_ratio=None)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.BOLD) is Verdict.NEEDS_REVIEW

    def test_unknown_field_positions_are_reviewed_not_passed(self) -> None:
        layout = GOOD_LAYOUT.replace(field_sides={})
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert verdict_for(report.checks, WarningCheckName.FIELD_OF_VISION) is Verdict.NEEDS_REVIEW


class TestAbsentWarning:
    def test_every_check_fails_when_there_is_no_warning(self) -> None:
        report = check_warning(detected=None, layout=GOOD_LAYOUT)
        assert all(c.verdict is Verdict.FAIL for c in report.checks)

    def test_the_reason_says_it_was_not_found_rather_than_naming_a_format_rule(self) -> None:
        report = check_warning(detected=None, layout=GOOD_LAYOUT)
        assert "not found" in report.field_result.reason.lower()
        for check in report.checks:
            assert "not found" in check.reason.lower() or "no warning" in check.reason.lower()


class TestFieldResult:
    def test_the_field_result_takes_the_worst_verdict(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_prefix_stroke_ratio=1.0)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert report.field_result.verdict is Verdict.FAIL

    def test_needs_review_wins_over_pass_but_loses_to_fail(self) -> None:
        layout = GOOD_LAYOUT.replace(warning_prefix_stroke_ratio=1.10)
        report = check_warning(detected=STATUTORY_WARNING, layout=layout)
        assert report.field_result.verdict is Verdict.NEEDS_REVIEW

    def test_the_declared_value_is_the_statutory_text(self) -> None:
        report = check_warning(detected=STATUTORY_WARNING, layout=GOOD_LAYOUT)
        assert report.field_result.declared == STATUTORY_WARNING
        assert report.field_result.field == "government_warning"

    def test_every_check_carries_a_sentence(self) -> None:
        for detected in (STATUTORY_WARNING, None, "Government Warning: nope"):
            report = check_warning(detected=detected, layout=GOOD_LAYOUT)
            for check in report.checks:
                assert check.reason.strip().endswith(".")
                assert len(check.reason) > 15
