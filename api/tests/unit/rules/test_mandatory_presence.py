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
