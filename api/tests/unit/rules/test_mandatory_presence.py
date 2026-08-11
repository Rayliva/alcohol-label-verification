"""A mandatory element missing from the label is a violation, not a blank.

The engine compared two documents, so when neither the application nor the
label mentioned a field it concluded there was nothing to compare and returned
NEEDS_REVIEW. But a label is not judged against the application alone — parts
of it are required by regulation whatever the application happens to say. Net
contents absent from a bottle is a violation even if nobody typed it into the
form, and treating that as "nothing to compare" hides it behind a shrug.

Country of origin is the conditional version of the same idea. It is not
demanded of a Kentucky bourbon, but a label reading "IMPORTED BY ..." has told
us it is an import, and 19 CFR 134.11 requires an imported article to be marked
with its country of origin.
"""

from __future__ import annotations

import pytest

from app.rules.engine import Application, LabelObservation, evaluate
from app.rules.types import Verdict

WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)

COMPLETE = {
    "brand_name": "OLD TOM DISTILLERY",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45% Alc./Vol. (90 Proof)",
    "net_contents": "750 mL",
    "bottler_address": "BOTTLED BY OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY",
    "government_warning": WARNING,
}


def verdict_for(field: str, *, label: dict, application: dict) -> Verdict:
    report = evaluate(
        Application(beverage_type="spirits", fields=application),
        LabelObservation(fields=label, layout=None),
    )
    return next(f.verdict for f in report.fields if f.field == field)


class TestARequiredElementMustBeOnTheLabel:
    def test_absent_from_both_documents_is_still_a_violation(self) -> None:
        label = {**COMPLETE, "net_contents": None}
        application = {k: v for k, v in COMPLETE.items() if k != "net_contents"}
        assert verdict_for("net_contents", label=label, application=application) is Verdict.FAIL

    def test_absent_from_the_label_alone_is_a_violation(self) -> None:
        label = {**COMPLETE, "net_contents": None}
        assert verdict_for("net_contents", label=label, application=COMPLETE) is Verdict.FAIL

    def test_present_and_matching_still_passes(self) -> None:
        assert verdict_for("net_contents", label=COMPLETE, application=COMPLETE) is Verdict.PASS


IMPORTED = {
    **COMPLETE,
    "bottler_address": "IMPORTED BY MERIDIAN SPIRITS IMPORTS, NEWARK, NJ",
}


class TestAnImportMustNameItsCountry:
    def test_an_imported_label_with_no_country_fails(self) -> None:
        # 19 CFR 134.11. The label said it was imported; it never said from where.
        application = {k: v for k, v in IMPORTED.items() if k != "country_of_origin"}
        assert (
            verdict_for("country_of_origin", label=IMPORTED, application=application)
            is Verdict.FAIL
        )

    def test_an_imported_label_that_names_its_country_passes(self) -> None:
        label = {**IMPORTED, "country_of_origin": "PRODUCT OF SCOTLAND"}
        application = {**IMPORTED, "country_of_origin": "PRODUCT OF SCOTLAND"}
        assert (
            verdict_for("country_of_origin", label=label, application=application) is Verdict.PASS
        )

    def test_a_domestic_label_is_not_asked_for_a_country(self) -> None:
        # The whole reason this field is conditional. Demanding it of a
        # Kentucky bourbon would be a false violation on every domestic label.
        report = evaluate(
            Application(beverage_type="spirits", fields=COMPLETE),
            LabelObservation(fields=COMPLETE, layout=None),
        )
        assert not [f for f in report.fields if f.field == "country_of_origin"]


class TestImportIsRecognisedHoweverItIsWorded:
    """The first version matched two exact phrases, so a label reading
    "IMPORTED AND BOTTLED BY" skipped the country check and passed — and the
    field never appeared in the report, so the agent was not told it had been
    skipped. Real labels use many wordings."""

    @pytest.mark.parametrize(
        "bottler",
        [
            "IMPORTED BY MERIDIAN SPIRITS IMPORTS, NEWARK, NJ",
            "IMPORTED AND BOTTLED BY ACME SPIRITS, NEW YORK, NY",
            "IMPORTED EXCLUSIVELY BY ACME SPIRITS, NEW YORK, NY",
            "SOLE U.S. IMPORTER: ACME SPIRITS, NEW YORK, NY",
            "Imported from Scotland by Acme Spirits",
            "BOTTLED IN SCOTLAND, IMPORTER ACME SPIRITS",
        ],
    )
    def test_an_import_with_no_country_named_fails(self, bottler: str) -> None:
        label = {**COMPLETE, "bottler_address": bottler}
        application = {k: v for k, v in label.items() if k != "country_of_origin"}
        assert (
            verdict_for("country_of_origin", label=label, application=application) is Verdict.FAIL
        )

    @pytest.mark.parametrize(
        "bottler",
        [
            "BOTTLED BY OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY",
            "DISTILLED AND BOTTLED BY OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY",
            "PRODUCED BY OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY",
        ],
    )
    def test_a_domestic_label_is_still_not_asked_for_a_country(self, bottler: str) -> None:
        # The reason the field is conditional at all. Demanding a country of
        # origin of a Kentucky bourbon is a false violation on every domestic
        # label in the queue.
        label = {**COMPLETE, "bottler_address": bottler}
        report = evaluate(
            Application(beverage_type="spirits", fields=label),
            LabelObservation(fields=label, layout=None),
        )
        assert not [f for f in report.fields if f.field == "country_of_origin"]

    def test_the_word_is_only_looked_for_where_it_means_something(self) -> None:
        # A brand called "Importers Reserve" is not a customs declaration. The
        # statement lives on the bottler line, so that is where it is read.
        label = {**COMPLETE, "brand_name": "IMPORTERS RESERVE"}
        report = evaluate(
            Application(beverage_type="spirits", fields=label),
            LabelObservation(fields=label, layout=None),
        )
        assert not [f for f in report.fields if f.field == "country_of_origin"]
