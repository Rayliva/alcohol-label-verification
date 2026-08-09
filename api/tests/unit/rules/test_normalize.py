"""Normalization strips differences that carry no meaning.

This is step one of fuzzy matching: be lenient about formatting, strict about
content. Everything here is deterministic — no scoring, no thresholds.
"""

from __future__ import annotations

import pytest

from app.rules.normalize import normalize


class TestNormalizeRemovesMeaninglessDifferences:
    def test_case_is_ignored(self) -> None:
        assert normalize("STONE'S THROW") == normalize("Stone's Throw")

    def test_curly_and_straight_apostrophes_are_equivalent(self) -> None:
        assert normalize("Stone’s Throw") == normalize("Stone's Throw")

    def test_curly_double_quotes_are_equivalent(self) -> None:
        assert normalize("“Special” Reserve") == normalize('"Special" Reserve')

    def test_repeated_whitespace_collapses(self) -> None:
        assert normalize("OLD   TOM\n\nDISTILLERY") == normalize("OLD TOM DISTILLERY")

    def test_leading_and_trailing_whitespace_is_stripped(self) -> None:
        assert normalize("  750 mL  ") == normalize("750 mL")

    def test_accents_are_folded(self) -> None:
        assert normalize("Café Réserve") == normalize("Cafe Reserve")

    def test_trailing_punctuation_is_dropped(self) -> None:
        assert normalize("Bardstown, Kentucky.") == normalize("Bardstown, Kentucky")

    def test_non_breaking_space_matches_a_normal_space(self) -> None:
        assert normalize("750 mL") == normalize("750 mL")

    def test_various_dashes_are_equivalent(self) -> None:
        assert normalize("Small–Batch") == normalize("Small-Batch")


class TestNormalizePreservesMeaning:
    def test_different_words_stay_different(self) -> None:
        assert normalize("Old Tom Distillery") != normalize("New Tom Distillery")

    def test_digits_are_preserved(self) -> None:
        assert normalize("45%") != normalize("54%")

    def test_internal_punctuation_that_separates_words_is_kept(self) -> None:
        # Collapsing this would make two distinct brands look identical.
        assert normalize("A.B.C. Distillery") != normalize("ABCD istillery")


class TestNormalizeEdgeCases:
    def test_empty_string(self) -> None:
        assert normalize("") == ""

    def test_whitespace_only_becomes_empty(self) -> None:
        assert normalize("   \n\t ") == ""

    @pytest.mark.parametrize("value", [None])
    def test_none_becomes_empty(self, value: None) -> None:
        assert normalize(value) == ""
