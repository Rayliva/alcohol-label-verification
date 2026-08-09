"""Fuzzy text matching: lenient about formatting, strict about content.

The governing example is from the brief — a senior agent's objection:

    "the brand name was 'STONE'S THROW' on the label but 'Stone's Throw' in
     the application. Technically a mismatch? Sure. But it's obviously the
     same thing. You need judgment."

A tool that fails that case gets ignored, so it is the first test here.
"""

from __future__ import annotations

from app.rules.match_text import match_text
from app.rules.types import Verdict


class TestFormattingDifferencesPass:
    def test_stones_throw_case_difference(self) -> None:
        """The brief's example. Non-negotiable."""
        result = match_text("brand_name", declared="Stone's Throw", detected="STONE'S THROW")
        assert result.verdict is Verdict.PASS

    def test_identical_strings(self) -> None:
        result = match_text("brand_name", declared="Old Tom", detected="Old Tom")
        assert result.verdict is Verdict.PASS
        assert result.confidence == 1.0

    def test_curly_apostrophe(self) -> None:
        result = match_text("brand_name", declared="Stone's Throw", detected="Stone’s Throw")
        assert result.verdict is Verdict.PASS

    def test_extra_whitespace(self) -> None:
        result = match_text("brand_name", declared="Old Tom", detected="Old   Tom")
        assert result.verdict is Verdict.PASS

    def test_trailing_period(self) -> None:
        result = match_text(
            "bottler_address",
            declared="Bardstown, Kentucky",
            detected="Bardstown, Kentucky.",
        )
        assert result.verdict is Verdict.PASS


class TestCorporateSuffixesAreReviewedNotFailed:
    def test_added_company_suffix(self) -> None:
        result = match_text(
            "brand_name", declared="Old Tom Distillery", detected="Old Tom Distillery Co."
        )
        assert result.verdict is Verdict.NEEDS_REVIEW

    def test_llc_suffix(self) -> None:
        result = match_text("brand_name", declared="Harbor Vodka", detected="Harbor Vodka LLC")
        assert result.verdict is Verdict.NEEDS_REVIEW


class TestGenuineDifferences:
    def test_one_letter_changed_needs_review(self) -> None:
        """Olde vs Old could be a typo either side — a human decides."""
        result = match_text(
            "brand_name", declared="Old Tom Distillery", detected="Olde Tom Distillery"
        )
        assert result.verdict is Verdict.NEEDS_REVIEW

    def test_different_word_fails(self) -> None:
        result = match_text(
            "brand_name", declared="Old Tom Distillery", detected="New Tom Distillery"
        )
        assert result.verdict is Verdict.FAIL

    def test_completely_different_fails(self) -> None:
        result = match_text("brand_name", declared="Old Tom", detected="Harbor Vodka")
        assert result.verdict is Verdict.FAIL


class TestMissingValues:
    def test_detected_missing_fails(self) -> None:
        result = match_text("brand_name", declared="Old Tom", detected=None)
        assert result.verdict is Verdict.FAIL
        assert "not" in result.reason.lower()

    def test_declared_missing_needs_review(self) -> None:
        """Nothing to compare against — the agent left the form field blank."""
        result = match_text("brand_name", declared=None, detected="Old Tom")
        assert result.verdict is Verdict.NEEDS_REVIEW

    def test_both_missing_needs_review(self) -> None:
        result = match_text("brand_name", declared=None, detected=None)
        assert result.verdict is Verdict.NEEDS_REVIEW


class TestResultShape:
    def test_carries_both_values_and_a_reason(self) -> None:
        result = match_text("brand_name", declared="Old Tom", detected="OLD TOM")
        assert result.field == "brand_name"
        assert result.declared == "Old Tom"
        assert result.detected == "OLD TOM"
        assert result.reason  # never empty — it is rendered to an agent
        assert 0.0 <= result.confidence <= 1.0

    def test_reason_is_a_plain_sentence(self) -> None:
        result = match_text("brand_name", declared="Old Tom", detected="New Tom")
        assert result.reason[0].isupper()
        assert result.reason.endswith(".")
