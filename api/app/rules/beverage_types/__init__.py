"""The beverage type registry.

Three rule sets, one engine. Look one up by name; the engine reads its field
list and never asks which beverage type it is holding.

See docs/specs/rule-engine.md 3.4
"""

from __future__ import annotations

from app.rules.beverage_types.base import (
    BeverageRules,
    FieldRule,
    Matcher,
    Requirement,
)
from app.rules.beverage_types.malt import MALT
from app.rules.beverage_types.spirits import SPIRITS
from app.rules.beverage_types.wine import WINE

__all__ = [
    "BeverageRules",
    "BeverageTypeUnavailableError",
    "FieldRule",
    "Matcher",
    "Requirement",
    "available_beverage_types",
    "rules_for",
]

_REGISTRY: dict[str, BeverageRules] = {
    rules.beverage_type: rules for rules in (SPIRITS, WINE, MALT)
}


class BeverageTypeUnavailableError(RuntimeError):
    """Raised when a registered but unshipped beverage type is submitted.

    Loud on purpose. Quietly checking a wine label against the spirits rule set
    would report violations that are not violations, which is worse than
    refusing — see .claude/rules/error-handling.md.
    """


def rules_for(beverage_type: str) -> BeverageRules:
    """Look up one beverage type's rule set.

    Raises KeyError for a type that does not exist, naming the ones that do.
    """
    try:
        return _REGISTRY[beverage_type]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(
            f"unknown beverage type {beverage_type!r}; known types are {known}"
        ) from None


def available_beverage_types() -> tuple[BeverageRules, ...]:
    """Every registered rule set, shipped or not.

    The unshipped ones are included deliberately: the UI shows them disabled,
    with their `unavailable_reason` beside them, rather than hiding the scope.
    """
    return tuple(_REGISTRY.values())
