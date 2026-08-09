"""Net contents matching for distilled spirits.

Verify net contents per 27 CFR 5.70.

That section deliberately permits several spellings of the same volume: "liter"
may be spelled "litre" or abbreviated "L"; "milliliters" may be abbreviated
"ml.", "mL." or "ML."; and U.S. customary equivalents such as fluid ounces may be
printed alongside the metric statement. None of those is a discrepancy, so the
comparison happens on normalised millilitres rather than on text.

Where a label prints both systems the metric statement is the mandatory
declaration, so that is the one compared.

Citations verified against Cornell LII on 2026-08-09.
See docs/specs/rule-engine.md 3.2 and .claude/rules/verify-regulations.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.rules.types import FieldResult, Verdict


class UnitSystem(StrEnum):
    METRIC = "metric"
    CUSTOMARY = "customary"


# U.S. customary volumes are exact by definition: the gallon is 231 cubic inches
# and the inch is 2.54 cm exactly, so every conversion below terminates.
_FLUID_OUNCE_ML = 29.5735295625
_PINT_ML = 473.176473
_QUART_ML = 946.352946
_GALLON_ML = 3785.411784

# Regex fragment -> (millilitres per unit, system). Fragments are matched in the
# order written; within each family the longer spellings come first so "liter"
# is never truncated to "l".
_UNIT_FRAGMENTS: tuple[tuple[str, float, UnitSystem], ...] = (
    (r"milli ?lit(?:er|re)s?", 1.0, UnitSystem.METRIC),
    (r"ml\.?", 1.0, UnitSystem.METRIC),
    (r"centi ?lit(?:er|re)s?", 10.0, UnitSystem.METRIC),
    (r"cl\.?", 10.0, UnitSystem.METRIC),
    (r"deci ?lit(?:er|re)s?", 100.0, UnitSystem.METRIC),
    (r"dl\.?", 100.0, UnitSystem.METRIC),
    (r"lit(?:er|re)s?", 1000.0, UnitSystem.METRIC),
    (r"l\.?", 1000.0, UnitSystem.METRIC),
    (r"fluid ounces?", _FLUID_OUNCE_ML, UnitSystem.CUSTOMARY),
    (r"fl\.? ?oz\.?", _FLUID_OUNCE_ML, UnitSystem.CUSTOMARY),
    (r"pints?", _PINT_ML, UnitSystem.CUSTOMARY),
    (r"pt\.?", _PINT_ML, UnitSystem.CUSTOMARY),
    (r"quarts?", _QUART_ML, UnitSystem.CUSTOMARY),
    (r"qt\.?", _QUART_ML, UnitSystem.CUSTOMARY),
    (r"gallons?", _GALLON_ML, UnitSystem.CUSTOMARY),
    (r"gal\.?", _GALLON_ML, UnitSystem.CUSTOMARY),
)

_QUANTITY = re.compile(
    r"(\d+(?:\.\d+)?)\s*(" + "|".join(f for f, _, _ in _UNIT_FRAGMENTS) + r")(?![a-z])",
    re.IGNORECASE,
)

# Two statements in the same system should be the same printed number; this is
# float slack, not a real allowance.
SAME_SYSTEM_TOLERANCE = 0.001
# Across systems the label is a rounded conversion of the same bottle:
# 750 mL prints as "25.4 fl oz", which is 751.17 mL.
CROSS_SYSTEM_TOLERANCE = 0.01


@dataclass(frozen=True)
class NetContents:
    """What could be read out of one net contents statement."""

    text: str
    millilitres: float | None
    system: UnitSystem | None


def _resolve(unit: str) -> tuple[float, UnitSystem]:
    """Map a matched unit back to its conversion factor."""
    for fragment, factor, system in _UNIT_FRAGMENTS:
        if re.fullmatch(fragment, unit, re.IGNORECASE):
            return factor, system
    raise AssertionError(f"matched unit {unit!r} is not in the fragment table")


def parse_net_contents(text: str | None) -> NetContents:
    """Recover a volume in millilitres from a free-text statement.

    A number with no unit parses to nothing: "750" could be millilitres or
    fluid ounces, and the two are a factor of thirty apart.
    """
    if not text or not text.strip():
        return NetContents(text="", millilitres=None, system=None)

    matches = [(float(m.group(1)), *_resolve(m.group(2))) for m in _QUANTITY.finditer(text)]
    if not matches:
        return NetContents(text=text, millilitres=None, system=None)

    # 27 CFR 5.70 treats the metric statement as the declaration and the
    # customary figure as an optional equivalent.
    metric = [m for m in matches if m[2] is UnitSystem.METRIC]
    quantity, factor, system = metric[0] if metric else matches[0]

    return NetContents(text=text, millilitres=quantity * factor, system=system)


def _fmt(millilitres: float) -> str:
    """Render a volume the way a person would say it: 750 mL, 751.2 mL."""
    return f"{round(millilitres, 1):g} mL"


def _describe(parsed: NetContents) -> str:
    """The statement as printed, with its millilitre value when they differ."""
    assert parsed.millilitres is not None
    printed = parsed.text.strip()
    converted = _fmt(parsed.millilitres)
    return (
        printed
        if printed.replace(" ", "").lower() == converted.replace(" ", "").lower()
        else (f"{printed} ({converted})")
    )


def _result(
    field: str,
    declared: str | None,
    detected: str | None,
    verdict: Verdict,
    confidence: float,
    reason: str,
) -> FieldResult:
    return FieldResult(
        field=field,
        declared=declared,
        detected=detected,
        verdict=verdict,
        confidence=confidence,
        reason=reason,
    )


def match_volume(field: str, *, declared: str | None, detected: str | None) -> FieldResult:
    """Compare the declared net contents against what the label states.

    Verify net contents per 27 CFR 5.70.
    """
    application = parse_net_contents(declared)
    label = parse_net_contents(detected)

    if not application.text and not label.text:
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            0.0,
            "No net contents were declared and none were found on the label. "
            "Every label must state them, so check the application.",
        )

    if not label.text:
        return _result(
            field,
            declared,
            detected,
            Verdict.FAIL,
            1.0,
            "Net contents were not found anywhere on the label. Distilled spirits "
            "labels must state the volume (27 CFR 5.63).",
        )

    if not application.text:
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            0.0,
            f"The label states {label.text.strip()}, but the application declared no "
            "net contents. Check the application.",
        )

    if label.millilitres is None:
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            0.0,
            f'No unit of measure could be read from "{label.text.strip()}" on the label. '
            "Compare it against the application yourself.",
        )

    if application.millilitres is None:
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            0.0,
            f"No unit of measure could be read from the declared value "
            f'"{application.text.strip()}". The label states {_fmt(label.millilitres)}.',
        )

    mixed_systems = application.system is not label.system
    tolerance = CROSS_SYSTEM_TOLERANCE if mixed_systems else SAME_SYSTEM_TOLERANCE
    largest = max(application.millilitres, label.millilitres)
    difference = abs(application.millilitres - label.millilitres)

    both = (
        f"The application declares {_describe(application)} and the label states "
        f"{_describe(label)}."
    )

    if difference > largest * tolerance:
        return _result(
            field, declared, detected, Verdict.FAIL, 1.0, f"{both} These are different volumes."
        )

    if application.text.strip().lower() == label.text.strip().lower():
        return _result(
            field,
            declared,
            detected,
            Verdict.PASS,
            1.0,
            f"The label and the application both give {_fmt(label.millilitres)}.",
        )

    return _result(
        field,
        declared,
        detected,
        Verdict.PASS,
        1.0,
        f"{both} The units are written differently but the volume is the same "
        f"({_fmt(label.millilitres)}).",
    )
