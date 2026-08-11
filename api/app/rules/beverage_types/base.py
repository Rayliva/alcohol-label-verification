"""The shape a beverage type's rule set takes.

Beverage types are **configuration, not code paths**. A spirits label, a wine
label and a malt beverage label are checked by the same engine reading three
different field lists. The alternative — an `if beverage_type == "wine"` inside
each matcher — emits false violations on two of the three categories, because
wine at 14% or less may legally omit its alcohol content and a plain malt
beverage needs none at all.

Only spirits carries content in Phase 1. Wine and malt are declared here with
their conditionals recorded and `available=False`, so the UI can disable their
buttons *and say why* (docs/ui-spec.md resolution 9). Sequencing the content is
cheap; retrofitting the shape later is not (PRD → Sequencing).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Requirement(StrEnum):
    """Whether a field has to be on the label."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    # Required only in circumstances the application does not tell us about —
    # imported goods, added nonbeverage ingredients, wine above 14%. Checked
    # when either document mentions it, never demanded outright.
    CONDITIONAL = "conditional"


class Matcher(StrEnum):
    """Which kind of comparison this field needs.

    Adding a field is a configuration edit. Adding a *kind* of comparison is a
    new matcher, which is a much rarer event.
    """

    TEXT = "text"
    ABV = "abv"
    VOLUME = "volume"
    WARNING = "warning"
    # Text, but a "product of"-style preamble is not part of the country.
    ORIGIN = "origin"


@dataclass(frozen=True)
class FieldRule:
    """One field on one beverage type's label."""

    field: str
    display_name: str
    matcher: Matcher
    requirement: Requirement
    citation: str
    # Shown to the agent beside a conditional field, in plain words.
    condition: str | None = None


@dataclass(frozen=True)
class BeverageRules:
    """Everything the engine needs to check one beverage type."""

    beverage_type: str
    display_name: str
    citation: str
    fields: tuple[FieldRule, ...]
    # 27 CFR 5.63 is a distilled spirits section; the same-field-of-vision
    # requirement does not travel to wine or malt.
    checks_field_of_vision: bool
    available: bool
    # Required when available is False. Rendered next to the disabled button,
    # because a disabled control that does not explain itself is a dead end
    # (.claude/rules/accessibility.md, rule 9).
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.available and not self.unavailable_reason:
            raise ValueError(
                f"{self.beverage_type} is marked unavailable but gives no reason. "
                "A disabled option must say why it is disabled."
            )
