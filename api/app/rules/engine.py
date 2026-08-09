"""The rule engine.

Takes two documents — what the application declared and what was read off the
artwork — walks the beverage type's configured field list, dispatches each field
to its matcher, and folds the results into one label outcome.

It never branches on beverage type. Everything that differs between spirits,
wine and malt lives in `beverage_types/` as data. See docs/specs/rule-engine.md
3.5.

Fields are addressed by name through a mapping rather than through typed
attributes, because that is what makes a new field a configuration edit instead
of a change to three dataclasses and a migration.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.rules.beverage_types import (
    BeverageRules,
    BeverageTypeUnavailableError,
    FieldRule,
    Matcher,
    Requirement,
    rules_for,
)
from app.rules.match_abv import match_abv
from app.rules.match_text import match_text
from app.rules.match_volume import match_volume
from app.rules.types import (
    FieldResult,
    LayoutMetrics,
    Verdict,
    WarningCheck,
    worst,
)
from app.rules.warning import check_warning


@dataclass(frozen=True)
class Application:
    """What the COLA application declared.

    `application_id` is TTB's own identifier, transcribed by the agent. We never
    generate it and never look anything up with it — there is no database. It is
    an opaque string echoed back into the results (docs/ui-spec.md resolution 5).
    """

    beverage_type: str
    fields: Mapping[str, str | None]
    application_id: str | None = None

    def get(self, name: str) -> str | None:
        return self.fields.get(name)


@dataclass(frozen=True)
class LabelObservation:
    """What was read off the artwork.

    `layout` is optional. Without it the text checks still run and the geometric
    ones return NEEDS_REVIEW — never PASS.
    """

    fields: Mapping[str, str | None]
    layout: LayoutMetrics | None = None

    def get(self, name: str) -> str | None:
        return self.fields.get(name)


@dataclass(frozen=True)
class LabelReport:
    """One label's outcome, ready to serialise for the UI."""

    beverage_type: str
    fields: tuple[FieldResult, ...]
    warning_checks: tuple[WarningCheck, ...]
    overall: Verdict
    application_id: str | None = None
    counts: Mapping[Verdict, int] = field(default_factory=dict)


def _applies(rule: FieldRule, declared: str | None, detected: str | None) -> bool:
    """Whether a conditional field should be checked at all.

    Imports, wine above 14%, malt with added nonbeverage ingredients — the
    application form does not tell us which of these we are looking at. So a
    conditional field is checked when either document mentions it and skipped
    when neither does. Demanding a country of origin on a Kentucky bourbon would
    be a false violation on every domestic label in the queue.
    """
    if rule.requirement is not Requirement.CONDITIONAL:
        return True
    return bool((declared or "").strip() or (detected or "").strip())


def evaluate(
    application: Application,
    observation: LabelObservation,
    rules: BeverageRules | None = None,
) -> LabelReport:
    """Check one label against one application.

    Raises BeverageTypeUnavailableError for a beverage type that is registered but
    not yet shipped, and KeyError for one that does not exist.
    """
    rules = rules or rules_for(application.beverage_type)
    if not rules.available:
        raise BeverageTypeUnavailableError(
            f"{rules.display_name} labels cannot be checked yet. {rules.unavailable_reason}"
        )

    results: list[FieldResult] = []
    warning_checks: tuple[WarningCheck, ...] = ()

    for rule in rules.fields:
        declared, detected = application.get(rule.field), observation.get(rule.field)
        if not _applies(rule, declared, detected):
            continue

        if rule.matcher is Matcher.WARNING:
            report = check_warning(
                detected=detected,
                layout=observation.layout,
                check_field_of_vision=rules.checks_field_of_vision,
            )
            results.append(report.field_result)
            warning_checks = report.checks
        elif rule.matcher is Matcher.ABV:
            results.append(match_abv(rule.field, declared=declared, detected=detected))
        elif rule.matcher is Matcher.VOLUME:
            results.append(match_volume(rule.field, declared=declared, detected=detected))
        else:
            results.append(match_text(rule.field, declared=declared, detected=detected))

    counts = {verdict: sum(1 for r in results if r.verdict is verdict) for verdict in Verdict}

    return LabelReport(
        beverage_type=rules.beverage_type,
        fields=tuple(results),
        warning_checks=warning_checks,
        overall=worst(r.verdict for r in results),
        application_id=application.application_id,
        counts=counts,
    )
