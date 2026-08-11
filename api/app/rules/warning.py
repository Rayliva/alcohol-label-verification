"""Government health warning verification.

Verify the health warning statement per 27 CFR 16.21 (text) and 16.22 (format).

The statutory text below was copied, not retyped, and verified against Cornell
LII on 2026-08-09. One wrong word here produces a confident, authoritative, wrong
answer — and the wrongness is invisible, because the output looks exactly like a
correct one. See .claude/rules/verify-regulations.md.

**Nothing in this module fuzzy-matches.** Whitespace is normalised, because a line
break on artwork is a layout artefact. Everything else is compared character for
character. Folding case here would pass the title-case violation that this product
exists to catch.

Six sub-checks, reported separately so an agent sees which rule was broken:

    text_exact       16.21   the wording
    caps             16.22   GOVERNMENT WARNING in capital letters
    bold             16.22   GOVERNMENT WARNING in bold
    proportion       16.22   readable relative to the text around it (a proxy)
    contrast         16.22   separated from its background
    field_of_vision   5.63   brand, class/type and alcohol content on one side

`proportion` is a **proxy**. 16.22 states absolute type sizes in millimetres
(1 mm at 237 mL or less, 2 mm through 3 L, 3 mm above), and millimetres are not
derivable from an uncalibrated photograph. The proportional check catches the
abuse pattern that actually occurs — a warning shrunk far below the surrounding
text — and the limitation is published rather than hidden (PRD OS-7).

See docs/specs/rule-engine.md 3.3
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from app.rules.normalize import normalize_whitespace_only
from app.rules.types import (
    FieldResult,
    LayoutMetrics,
    Verdict,
    WarningCheck,
    WarningCheckName,
    worst,
)

# 27 CFR 16.21, verbatim. One continuous statement; (1) and (2) are inline.
# Verified against Cornell LII 2026-08-09. Do not edit without re-verifying.
STATUTORY_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

WARNING_PREFIX = "GOVERNMENT WARNING"

FIELD = "government_warning"

# 27 CFR 5.63 — these three must appear in the same field of vision.
SAME_FIELD_OF_VISION = ("brand_name", "class_type", "alcohol_content")

# Set by the pipeline for a field that is not on the label at all.
ABSENT_SIDE = "absent"

# Calibrated against the corpus on 2026-08-09, replacing the guesses this file
# shipped with. None is a regulatory figure: the regulation states absolute
# millimetres, which an uncalibrated image cannot supply.
#
# Bold — measured stroke-thickness ratio: 1.35 on a compliant label, 1.06 on
# t2-warning-not-bold. The first guess (pass at 1.15) passed both.
BOLD_PASS_RATIO = 1.20
BOLD_REVIEW_RATIO = 1.10
#
# Proportion — measured warning height against the median height of the other
# text. Across the 49 corpus labels with ground-truth geometry, compliant
# warnings measure 0.525 to 0.610 and the shrunken variant measures 0.220.
# A compliant warning is legitimately smaller than the brand name and the body
# copy, so the original guess (pass at 0.80) failed every clean label. What the
# proxy has to catch is a warning shrunk far below the text around it, and the
# thresholds sit in the gap with margin on both sides.
PROPORTION_PASS_RATIO = 0.45
PROPORTION_REVIEW_RATIO = 0.30
#
# Contrast — WCAG ratio inside the warning region: 18.6 on a compliant label,
# 1.2 on t2-warning-low-contrast. The AA thresholds separate those comfortably
# and are the recognised figures, so they stand.
CONTRAST_PASS_RATIO = 4.5
CONTRAST_REVIEW_RATIO = 3.0

_CHECK_LABELS = {
    WarningCheckName.TEXT_EXACT: "the wording does not match 27 CFR 16.21",
    WarningCheckName.CAPS: "GOVERNMENT WARNING is not in capital letters",
    WarningCheckName.BOLD: "GOVERNMENT WARNING may not be bold",
    WarningCheckName.PROPORTION: "the warning may be too small next to the other text",
    WarningCheckName.CONTRAST: "the warning may not stand out from its background",
    WarningCheckName.FIELD_OF_VISION: (
        "brand, class/type and alcohol content may not be on one side"
    ),
}


@dataclass(frozen=True)
class WarningReport:
    """The warning as one field result plus its six sub-checks."""

    field_result: FieldResult
    checks: tuple[WarningCheck, ...]


def _first_difference(expected: str, actual: str) -> tuple[str, str]:
    """The first stretch of words that differs, as (expected, found).

    Reported to the agent so the answer is "you wrote X where the statute says Y"
    rather than "does not match", which sends them to read fifty words by eye.
    """
    expected_words, actual_words = expected.split(), actual.split()
    matcher = SequenceMatcher(None, expected_words, actual_words, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        return (
            " ".join(expected_words[i1 : i2 + 2]) or "(nothing)",
            " ".join(actual_words[j1 : j2 + 2]) or "(nothing)",
        )
    return ("", "")


def _check_text(detected: str) -> WarningCheck:
    """27 CFR 16.21 — the wording, character for character."""
    if normalize_whitespace_only(detected) == STATUTORY_WARNING:
        return WarningCheck(
            WarningCheckName.TEXT_EXACT,
            Verdict.PASS,
            "The wording matches 27 CFR 16.21 exactly.",
        )
    expected, found = _first_difference(STATUTORY_WARNING, normalize_whitespace_only(detected))
    return WarningCheck(
        WarningCheckName.TEXT_EXACT,
        Verdict.FAIL,
        "The wording differs from the statutory text in 27 CFR 16.21. The statute "
        f'reads "{expected}"; the label reads "{found}". The warning must appear '
        "word for word.",
    )


def _check_caps(detected: str) -> WarningCheck:
    """27 CFR 16.22 — GOVERNMENT WARNING in capital letters.

    Whitespace is collapsed first, and only whitespace. A label that wraps
    between GOVERNMENT and WARNING would otherwise be reported as carrying no
    heading at all, while the exact-text check on the same label said PASS —
    two checks contradicting each other destroys the agent's trust in both.
    """
    detected = normalize_whitespace_only(detected)
    position = detected.upper().find(WARNING_PREFIX)
    if position == -1:
        return WarningCheck(
            WarningCheckName.CAPS,
            Verdict.FAIL,
            'The label does not carry a "GOVERNMENT WARNING" heading at all, which '
            "27 CFR 16.22 requires in capital letters.",
        )
    as_printed = detected[position : position + len(WARNING_PREFIX)]
    if as_printed == WARNING_PREFIX:
        return WarningCheck(
            WarningCheckName.CAPS,
            Verdict.PASS,
            "GOVERNMENT WARNING is in capital letters.",
        )
    return WarningCheck(
        WarningCheckName.CAPS,
        Verdict.FAIL,
        f'The label reads "{as_printed}". 27 CFR 16.22 requires GOVERNMENT WARNING '
        "in capital letters.",
    )


def _check_bold(layout: LayoutMetrics | None) -> WarningCheck:
    """27 CFR 16.22 — GOVERNMENT WARNING in bold, by relative stroke weight."""
    ratio = layout.warning_prefix_stroke_ratio if layout else None
    if ratio is None:
        return WarningCheck(
            WarningCheckName.BOLD,
            Verdict.NEEDS_REVIEW,
            "Stroke weight could not be measured on this image, so whether "
            "GOVERNMENT WARNING is bold was not established. Check it by eye.",
        )
    if ratio >= BOLD_PASS_RATIO:
        return WarningCheck(
            WarningCheckName.BOLD,
            Verdict.PASS,
            f"GOVERNMENT WARNING is {ratio:.2f} times the stroke weight of the "
            "surrounding text, which reads as bold.",
        )
    if ratio >= BOLD_REVIEW_RATIO:
        return WarningCheck(
            WarningCheckName.BOLD,
            Verdict.NEEDS_REVIEW,
            f"GOVERNMENT WARNING is only {ratio:.2f} times the stroke weight of the "
            "surrounding text. That is close to the line — look at it.",
        )
    return WarningCheck(
        WarningCheckName.BOLD,
        Verdict.FAIL,
        f"GOVERNMENT WARNING is {ratio:.2f} times the stroke weight of the "
        "surrounding text, so it is not bold. 27 CFR 16.22 requires bold.",
    )


def _check_proportion(layout: LayoutMetrics | None) -> WarningCheck:
    """27 CFR 16.22 — readable size, checked proportionally. See module docstring."""
    warning_height = layout.warning_text_height if layout else None
    body_height = layout.median_text_height if layout else None
    if not warning_height or not body_height:
        return WarningCheck(
            WarningCheckName.PROPORTION,
            Verdict.NEEDS_REVIEW,
            "Text heights could not be measured on this image, so the size of the "
            "warning was not established. Check it by eye.",
        )
    ratio = warning_height / body_height
    if ratio >= PROPORTION_PASS_RATIO:
        return WarningCheck(
            WarningCheckName.PROPORTION,
            Verdict.PASS,
            f"The warning is {ratio:.0%} of the height of the other text on the label.",
        )
    if ratio >= PROPORTION_REVIEW_RATIO:
        return WarningCheck(
            WarningCheckName.PROPORTION,
            Verdict.NEEDS_REVIEW,
            f"The warning is {ratio:.0%} of the height of the other text on the label, "
            "which is small enough to be worth a look.",
        )
    return WarningCheck(
        WarningCheckName.PROPORTION,
        Verdict.FAIL,
        f"The warning is only {ratio:.0%} of the height of the other text on the "
        "label. 27 CFR 16.22 requires it to be readable and conspicuous.",
    )


def _check_contrast(layout: LayoutMetrics | None) -> WarningCheck:
    """27 CFR 16.22 — separated from its background by contrast."""
    ratio = layout.warning_contrast_ratio if layout else None
    if ratio is None:
        return WarningCheck(
            WarningCheckName.CONTRAST,
            Verdict.NEEDS_REVIEW,
            "Contrast could not be measured on this image, so whether the warning "
            "stands out from its background was not established. Check it by eye.",
        )
    if ratio >= CONTRAST_PASS_RATIO:
        return WarningCheck(
            WarningCheckName.CONTRAST,
            Verdict.PASS,
            f"The warning contrasts with its background at {ratio:.1f} to 1.",
        )
    if ratio >= CONTRAST_REVIEW_RATIO:
        return WarningCheck(
            WarningCheckName.CONTRAST,
            Verdict.NEEDS_REVIEW,
            f"The warning contrasts with its background at only {ratio:.1f} to 1. "
            "Look at whether it reads clearly on the printed label.",
        )
    return WarningCheck(
        WarningCheckName.CONTRAST,
        Verdict.FAIL,
        f"The warning barely separates from its background ({ratio:.1f} to 1). "
        "27 CFR 16.22 requires it to contrast sufficiently to be conspicuous.",
    )


def _check_field_of_vision(layout: LayoutMetrics | None) -> WarningCheck:
    """27 CFR 5.63 — brand, class/type and alcohol content on one side."""
    sides = layout.field_sides if layout else {}
    # A field that is not on the label at all fails its own check. Repeating it
    # here would report one violation twice and make the label look worse than
    # it is.
    applicable = [name for name in SAME_FIELD_OF_VISION if sides.get(name) != ABSENT_SIDE]
    known = {name: sides[name] for name in applicable if sides.get(name)}
    if len(known) < len(applicable):
        missing = [name for name in applicable if name not in known]
        return WarningCheck(
            WarningCheckName.FIELD_OF_VISION,
            Verdict.NEEDS_REVIEW,
            "It could not be established which side of the container carries "
            f"{', '.join(name.replace('_', ' ') for name in missing)}, so whether "
            "27 CFR 5.63 is met was not checked. Look at the artwork.",
        )
    if not known:
        return WarningCheck(
            WarningCheckName.FIELD_OF_VISION,
            Verdict.NEEDS_REVIEW,
            "None of the three fields 27 CFR 5.63 governs could be located on the "
            "artwork, so this was not checked. Look at the label.",
        )
    # One field cannot share a field of vision with anything. Saying so anyway
    # vouched for two fields that were not on the label — and their absence is
    # already reported by their own checks, so this must not repeat it as a
    # violation either.
    if len(known) < 2:
        present = ", ".join(name.replace("_", " ") for name in known)
        return WarningCheck(
            WarningCheckName.FIELD_OF_VISION,
            Verdict.NEEDS_REVIEW,
            f"Only {present} could be located on the artwork, so there is nothing "
            "to compare it against and 27 CFR 5.63 was not checked. The other "
            "fields are reported above.",
        )

    if len(set(known.values())) == 1:
        return WarningCheck(
            WarningCheckName.FIELD_OF_VISION,
            Verdict.PASS,
            (
                "Brand name, class or type, and alcohol content all appear on the "
                "same side of the container, as 27 CFR 5.63 requires."
                if len(known) == len(SAME_FIELD_OF_VISION)
                else (
                    "The fields found on the artwork ("
                    + ", ".join(n.replace("_", " ") for n in known)
                    + ") share one side of the container, as 27 CFR 5.63 requires."
                )
            ),
        )
    placements = ", ".join(
        f"{name.replace('_', ' ')} on the {side}" for name, side in known.items()
    )
    return WarningCheck(
        WarningCheckName.FIELD_OF_VISION,
        Verdict.FAIL,
        f"27 CFR 5.63 requires brand name, class or type, and alcohol content in the "
        f"same field of vision, but this label has {placements}.",
    )


def _absent_warning_checks(check_field_of_vision: bool) -> tuple[WarningCheck, ...]:
    """Every check fails, and every one says why in the same terms.

    A missing warning is not a formatting problem, so no check reports one.
    """
    names = [
        WarningCheckName.TEXT_EXACT,
        WarningCheckName.CAPS,
        WarningCheckName.BOLD,
        WarningCheckName.PROPORTION,
        WarningCheckName.CONTRAST,
    ]
    if check_field_of_vision:
        names.append(WarningCheckName.FIELD_OF_VISION)
    return tuple(
        WarningCheck(
            name,
            Verdict.FAIL,
            "No warning was found on the label, so this could not be checked. Every "
            "alcohol beverage label must carry the statement in 27 CFR 16.21.",
        )
        for name in names
    )


def _summarise(detected: str | None, checks: tuple[WarningCheck, ...]) -> str:
    if detected is None or not detected.strip():
        return (
            "The government warning was not found on the label. Every alcohol "
            "beverage label must carry it (27 CFR 16.21)."
        )
    problems = [_CHECK_LABELS[c.check] for c in checks if c.verdict is not Verdict.PASS]
    if not problems:
        return (
            "The warning matches 27 CFR 16.21 exactly and meets the format requirements in 16.22."
        )
    return f"Check the warning: {'; '.join(problems)}."


def check_warning(
    *,
    detected: str | None,
    layout: LayoutMetrics | None,
    check_field_of_vision: bool = True,
) -> WarningReport:
    """Run every government warning check over one label.

    Verify the health warning statement per 27 CFR 16.21 and 16.22.

    `check_field_of_vision` is False for beverage types 27 CFR 5.63 does not
    govern; the sub-check is then omitted rather than passed.
    """
    if detected is None or not detected.strip():
        checks = _absent_warning_checks(check_field_of_vision)
    else:
        checks = (
            _check_text(detected),
            _check_caps(detected),
            _check_bold(layout),
            _check_proportion(layout),
            _check_contrast(layout),
        )
        if check_field_of_vision:
            checks = (*checks, _check_field_of_vision(layout))

    return WarningReport(
        field_result=FieldResult(
            field=FIELD,
            declared=STATUTORY_WARNING,
            detected=detected,
            verdict=worst(c.verdict for c in checks),
            confidence=1.0,
            reason=_summarise(detected, checks),
        ),
        checks=checks,
    )
