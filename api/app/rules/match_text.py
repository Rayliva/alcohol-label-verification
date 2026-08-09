"""Fuzzy text matching.

Lenient about formatting, strict about content. Two stages:

  1. Normalize away provably meaningless differences (deterministic).
  2. Score whatever still differs, and threshold into three states.

The thresholds are starting points from PRD A-4, to be tuned against the
labeled corpus. They are named constants rather than inline numbers so a
tuning pass changes one place and the accuracy suite catches the fallout.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.rules.normalize import normalize
from app.rules.types import FieldResult, Verdict

# PRD A-4. Provisional until tuned — see .claude/skills/benchmark-latency.md
PASS_THRESHOLD = 0.95
REVIEW_THRESHOLD = 0.80

# Dropped only when comparing a second time, to tell "same company, longer
# legal name" apart from "different company". Never dropped from what the
# agent sees.
_CORPORATE_SUFFIXES = (
    "co",
    "co.",
    "company",
    "inc",
    "inc.",
    "incorporated",
    "llc",
    "l.l.c.",
    "ltd",
    "ltd.",
    "limited",
    "corp",
    "corp.",
    "corporation",
    "plc",
)

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def similarity(left: str, right: str) -> float:
    """Normalized similarity in 0..1 over already-normalized strings."""
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _strip_corporate_suffix(value: str) -> str:
    tokens = _TOKEN.findall(value)
    while tokens and tokens[-1] in {s.replace(".", "") for s in _CORPORATE_SUFFIXES}:
        tokens.pop()
    return " ".join(tokens)


def match_text(field: str, *, declared: str | None, detected: str | None) -> FieldResult:
    """Compare a declared value against what was read from the label."""
    left, right = normalize(declared), normalize(detected)

    if not right and not left:
        return FieldResult(
            field=field,
            declared=declared,
            detected=detected,
            verdict=Verdict.NEEDS_REVIEW,
            confidence=0.0,
            reason="Nothing was declared for this field and nothing was found on the label.",
        )

    if not right:
        return FieldResult(
            field=field,
            declared=declared,
            detected=detected,
            verdict=Verdict.FAIL,
            confidence=1.0,
            reason="This was not found anywhere on the label.",
        )

    if not left:
        return FieldResult(
            field=field,
            declared=declared,
            detected=detected,
            verdict=Verdict.NEEDS_REVIEW,
            confidence=0.0,
            reason=(
                "The label shows a value here, but the application did not declare one. "
                "Check the application."
            ),
        )

    # Everything normalization can forgive has already been forgiven. If the
    # strings still differ, a human decides — the only question left is
    # whether this is REVIEW or FAIL.
    if left == right:
        return FieldResult(
            field=field,
            declared=declared,
            detected=detected,
            verdict=Verdict.PASS,
            confidence=1.0,
            reason=(
                "Matches exactly."
                if (declared or "") == (detected or "")
                else "Matches once formatting differences are ignored."
            ),
        )

    score = similarity(left, right)

    # A longer legal name is a judgment call, not a mismatch.
    if _strip_corporate_suffix(left) == _strip_corporate_suffix(right):
        return FieldResult(
            field=field,
            declared=declared,
            detected=detected,
            verdict=Verdict.NEEDS_REVIEW,
            confidence=score,
            reason=(
                "The names match apart from a company suffix such as Co. or LLC. "
                "Confirm they refer to the same business."
            ),
        )

    # An address with the state abbreviated is almost certainly the same
    # address. Failing it sends an agent to reject an application over a
    # formatting choice, which is how a tool loses their trust.
    if _differs_only_by_abbreviation(left, right):
        return FieldResult(
            field=field,
            declared=declared,
            detected=detected,
            verdict=Verdict.NEEDS_REVIEW,
            confidence=score,
            reason=(
                "The two agree except that one shortens a word the other spells out. "
                "Confirm they mean the same thing."
            ),
        )

    # Token-aware: a whole word replaced is a mismatch; a character difference
    # inside a word is a possible typo on either side. Character similarity
    # alone cannot tell these apart — "Old"->"Olde" scores higher than
    # "Old"->"New", but only one of them is a genuine discrepancy.
    if _has_wholly_different_word(left, right):
        return FieldResult(
            field=field,
            declared=declared,
            detected=detected,
            verdict=Verdict.FAIL,
            confidence=score,
            reason="The label does not match what the application declared.",
        )

    if score >= REVIEW_THRESHOLD:
        return FieldResult(
            field=field,
            declared=declared,
            detected=detected,
            verdict=Verdict.NEEDS_REVIEW,
            confidence=score,
            reason=(
                "Close but not identical. This may be a typing difference or a "
                "misread character. Compare the two values and decide."
            ),
        )

    return FieldResult(
        field=field,
        declared=declared,
        detected=detected,
        verdict=Verdict.FAIL,
        confidence=score,
        reason="The label does not match what the application declared.",
    )


# Below this, two tokens in the same position are different words rather than
# the same word misspelled. Provisional (PRD A-4); tune against the corpus.
_TYPO_THRESHOLD = 0.7


def _is_abbreviation_of(short: str, long: str) -> bool:
    """True when `short` reads as a shortening of `long`.

    Covers the two forms that actually appear on labels: a truncation ("Kent."
    for "Kentucky") and an initialism keeping the first letter and some later
    ones in order ("KY"). Requires the first letter to match, so "Tennessee"
    never reads as a shortening of "Kentucky".
    """
    if len(short) < 2 or len(short) >= len(long) or short[0] != long[0]:
        return False
    position = 0
    for character in short:
        position = long.find(character, position)
        if position == -1:
            return False
        position += 1
    return True


def _differs_only_by_abbreviation(left: str, right: str) -> bool:
    """True when every differing token pair is one word and its shortening."""
    left_tokens, right_tokens = _TOKEN.findall(left), _TOKEN.findall(right)
    if len(left_tokens) != len(right_tokens):
        return False
    differing = [(lt, rt) for lt, rt in zip(left_tokens, right_tokens, strict=True) if lt != rt]
    if not differing:
        return False
    return all(_is_abbreviation_of(lt, rt) or _is_abbreviation_of(rt, lt) for lt, rt in differing)


def _has_wholly_different_word(left: str, right: str) -> bool:
    """True when a token was replaced outright rather than mistyped."""
    left_tokens, right_tokens = _TOKEN.findall(left), _TOKEN.findall(right)
    if len(left_tokens) != len(right_tokens):
        # Different word counts — fall back to whole-string similarity.
        return similarity(left, right) < REVIEW_THRESHOLD
    return any(
        lt != rt and similarity(lt, rt) < _TYPO_THRESHOLD
        for lt, rt in zip(left_tokens, right_tokens, strict=True)
    )
