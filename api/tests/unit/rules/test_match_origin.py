"""A country of origin is the country, however the application phrases it.

Applications write "PRODUCT OF ENGLAND"; labels print "ENGLAND". Reading that
as a mismatch fails a compliant imported label on a wording convention, which
is the tool making an agent's job harder rather than easier — Dave Morrison's
objection, and the same shape as the STONE'S THROW case the brief names.
"""

from __future__ import annotations

import pytest

from app.rules.match_origin import match_origin
from app.rules.types import Verdict


class TestThePreambleIsNotPartOfTheCountry:
    @pytest.mark.parametrize(
        "declared",
        [
            "PRODUCT OF ENGLAND",
            "Produced in England",
            "DISTILLED IN ENGLAND",
            "MADE IN ENGLAND",
            "IMPORTED FROM ENGLAND",
            "A PRODUCT OF ENGLAND",
        ],
    )
    def test_a_declared_preamble_still_matches_the_bare_country(self, declared: str) -> None:
        result = match_origin("country_of_origin", declared=declared, detected="ENGLAND")
        assert result.verdict is Verdict.PASS

    def test_it_works_the_other_way_round(self) -> None:
        # The label carries the preamble and the application does not.
        result = match_origin(
            "country_of_origin", declared="England", detected="PRODUCT OF ENGLAND"
        )
        assert result.verdict is Verdict.PASS


class TestARealMismatchStillFails:
    def test_a_different_country_does_not_pass(self) -> None:
        result = match_origin(
            "country_of_origin", declared="PRODUCT OF ENGLAND", detected="PRODUCT OF SCOTLAND"
        )
        assert result.verdict is not Verdict.PASS

    def test_stripping_the_preamble_cannot_empty_the_field(self) -> None:
        # "PRODUCT OF" alone names no country. Reducing it to nothing and then
        # matching another empty value would invent agreement.
        result = match_origin("country_of_origin", declared="PRODUCT OF", detected="PRODUCT OF")
        assert result.verdict is not Verdict.FAIL
        assert result.detected == "PRODUCT OF"
