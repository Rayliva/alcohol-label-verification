"""Alcohol content matching for distilled spirits.

Verify alcohol content per 27 CFR 5.65, with proof per 27 CFR 5.1.

Two independent questions, answered in this order:

  1. **Does the label agree with itself?** 27 CFR 5.1 defines proof as "the ethyl
     alcohol content of a liquid at 60 degrees Fahrenheit, stated as twice the
     percentage of ethyl alcohol by volume". A label reading 45% and 80 proof is
     defective on its own terms, whatever the application says.
  2. **Does the label agree with the application?** Both are documents. They
     should agree exactly.

The regulatory +/-0.3 point tolerance in 5.65 answers neither question: it governs
the labelled figure against the liquid in the bottle, lab-verified. It appears in
this module only as context inside a NEEDS_REVIEW reason, never as a pass rule.

Citations verified against Cornell LII on 2026-08-09.
See docs/specs/rule-engine.md 3.1 and .claude/rules/verify-regulations.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.rules.types import FieldResult, Verdict

# 27 CFR 5.65 permits "alc", "%", "/" for "by", and "vol" as abbreviations, so the
# surrounding words vary widely. The percent sign or the word "percent" is the only
# reliable marker of the mandatory statement.
_ABV = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b)", re.IGNORECASE)

# Proof appears as a word or as the degree symbol: "90 Proof", "90°", "Proof: 90".
_PROOF_AFTER = re.compile(r"(\d+(?:\.\d+)?)\s*(?:proof\b|°)", re.IGNORECASE)
_PROOF_BEFORE = re.compile(r"proof\b\s*:?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)

# 27 CFR 5.65. Never applied as a pass rule — see the module docstring.
LIQUID_TOLERANCE_POINTS = 0.3

# Floating point slack only. Two label statements that differ by less than this
# are the same printed number.
_EPSILON = 1e-6


@dataclass(frozen=True)
class AlcoholContent:
    """What could be read out of one alcohol content statement."""

    text: str
    abv: float | None
    proof: float | None

    @property
    def is_readable(self) -> bool:
        return self.abv is not None or self.proof is not None


def parse_alcohol_content(text: str | None) -> AlcoholContent:
    """Recover the percentage and any proof figure from a free-text statement.

    A bare number parses to nothing. "45" could be a percentage or a proof, and
    guessing produces a confident wrong answer that looks exactly like a right one.
    """
    if not text or not text.strip():
        return AlcoholContent(text="", abv=None, proof=None)

    abv_match = _ABV.search(text)
    proof_match = _PROOF_AFTER.search(text) or _PROOF_BEFORE.search(text)

    return AlcoholContent(
        text=text,
        abv=float(abv_match.group(1)) if abv_match else None,
        proof=float(proof_match.group(1)) if proof_match else None,
    )


def _fmt(value: float) -> str:
    """Render a number the way a label prints it: 45.0 -> 45, 45.5 -> 45.5."""
    return f"{value:g}"


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


def match_abv(field: str, *, declared: str | None, detected: str | None) -> FieldResult:
    """Compare the declared alcohol content against what the label states.

    Verify alcohol content per 27 CFR 5.65; proof relationship per 27 CFR 5.1.
    """
    application = parse_alcohol_content(declared)
    label = parse_alcohol_content(detected)

    if not application.text and not label.text:
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            0.0,
            "No alcohol content was declared and none was found on the label. "
            "Distilled spirits labels must state it, so check the application.",
        )

    if not label.text:
        return _result(
            field,
            declared,
            detected,
            Verdict.FAIL,
            1.0,
            "Alcohol content was not found anywhere on the label. Distilled spirits "
            "must state it as a percentage by volume (27 CFR 5.63).",
        )

    if not application.text:
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            0.0,
            f"The label states {label.text}, but the application declared no alcohol "
            "content. Check the application.",
        )

    if not label.is_readable:
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            0.0,
            f'No percentage or proof could be read from "{label.text}" on the label. '
            "Compare it against the application yourself.",
        )

    # 27 CFR 5.65 makes the percentage statement mandatory. Proof alone is not it.
    if label.abv is None and label.proof is not None:
        return _result(
            field,
            declared,
            detected,
            Verdict.FAIL,
            1.0,
            f"The label states {_fmt(label.proof)} proof but never gives the alcohol "
            "content as a percentage by volume, which 27 CFR 5.65 requires.",
        )

    assert label.abv is not None  # the two branches above exhaust the alternatives

    # The label against itself, before the label against the form: a statement that
    # contradicts itself is defective whatever the application says.
    if label.proof is not None and abs(label.proof - 2 * label.abv) > _EPSILON:
        return _result(
            field,
            declared,
            detected,
            Verdict.FAIL,
            1.0,
            f"The label says {_fmt(label.abv)}% alcohol by volume but "
            f"{_fmt(label.proof)} proof. Proof is twice the percentage, so "
            f"{_fmt(label.abv)}% should read {_fmt(2 * label.abv)} proof.",
        )

    if application.abv is None:
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            0.0,
            f'No percentage could be read from the declared value "{application.text}". '
            f"The label states {_fmt(label.abv)}%. Compare them yourself.",
        )

    difference = abs(application.abv - label.abv)

    if difference > _EPSILON:
        both = (
            f"The application declares {_fmt(application.abv)}% alcohol by volume "
            f"and the label states {_fmt(label.abv)}%."
        )
        if difference > LIQUID_TOLERANCE_POINTS:
            return _result(field, declared, detected, Verdict.FAIL, 1.0, f"{both} They differ.")
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            1.0,
            f"{both} The 0.3 point tolerance in 27 CFR 5.65 applies to the liquid in "
            "the bottle, not to the difference between two documents, so this needs a "
            "human decision.",
        )

    if application.proof is not None and label.proof is None:
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            1.0,
            f"The percentages match at {_fmt(label.abv)}%. The application also declares "
            f"{_fmt(application.proof)} proof, which does not appear on the label. Proof "
            "is optional, so confirm this is intended.",
        )

    if (
        application.proof is not None
        and label.proof is not None
        and abs(application.proof - label.proof) > _EPSILON
    ):
        return _result(
            field,
            declared,
            detected,
            Verdict.NEEDS_REVIEW,
            1.0,
            f"The percentages match at {_fmt(label.abv)}%, but the application declares "
            f"{_fmt(application.proof)} proof and the label states "
            f"{_fmt(label.proof)} proof.",
        )

    return _result(
        field,
        declared,
        detected,
        Verdict.PASS,
        1.0,
        f"The label and the application both give {_fmt(label.abv)}% alcohol by volume.",
    )
