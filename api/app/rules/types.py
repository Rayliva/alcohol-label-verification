"""Vocabulary for the compliance engine.

This package is pure: it takes data and returns verdicts. It imports nothing
from `ocr` or `extraction`, which is what keeps it unit-testable with no
network and no mocks.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Verdict(StrEnum):
    """Three states, never two.

    Binary pass/fail is explicitly wrong for this product: a label reading
    STONE'S THROW against an application saying Stone's Throw is a PASS, not a
    failure. NEEDS_REVIEW is where judgment belongs. (PRD FR-11)
    """

    PASS = "pass"
    NEEDS_REVIEW = "needs_review"
    FAIL = "fail"


@dataclass(frozen=True)
class FieldResult:
    """One field's outcome.

    `reason` is rendered verbatim in the UI. Write it as a plain sentence an
    agent can act on — it is read by a compliance officer, not a developer.
    """

    field: str
    declared: str | None
    detected: str | None
    verdict: Verdict
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in 0..1, got {self.confidence}")


# Worst wins. One FAIL makes a label FAIL; short of that, one NEEDS_REVIEW makes
# it NEEDS_REVIEW. Averaging verdicts would let a page of passes bury a violation.
_SEVERITY = {Verdict.PASS: 0, Verdict.NEEDS_REVIEW: 1, Verdict.FAIL: 2}


def worst(verdicts: Iterable[Verdict]) -> Verdict:
    """The most severe verdict in the collection; PASS when it is empty."""
    return max(verdicts, key=lambda v: _SEVERITY[v], default=Verdict.PASS)


class WarningCheckName(StrEnum):
    """The government warning is one field with six independent ways to fail.

    Reporting them separately is what lets an agent see *which* rule was broken
    rather than a single amber badge on the most important field on the label.
    (docs/ui-spec.md → Screen 3)
    """

    TEXT_EXACT = "text_exact"
    CAPS = "caps"
    BOLD = "bold"
    PROPORTION = "proportion"
    CONTRAST = "contrast"
    FIELD_OF_VISION = "field_of_vision"


@dataclass(frozen=True)
class WarningCheck:
    """One sub-check of the government warning."""

    check: WarningCheckName
    verdict: Verdict
    reason: str


@dataclass(frozen=True)
class LayoutMetrics:
    """Geometric facts that only an image can supply.

    The rule engine never touches pixels — the pipeline measures these and hands
    them over. Every value is optional, and a check with no measurement returns
    NEEDS_REVIEW rather than PASS: a geometric check that silently passes when it
    did not run is a false PASS, which is the error class this product is
    scored on.
    """

    warning_text_height: float | None = None
    median_text_height: float | None = None
    warning_prefix_stroke_ratio: float | None = None
    warning_contrast_ratio: float | None = None
    # Field name -> which side of the container it appeared on, for 27 CFR 5.63.
    field_sides: Mapping[str, str] = field(default_factory=dict)

    def replace(self, **changes: Any) -> LayoutMetrics:
        """A copy with some measurements changed."""
        return dataclasses.replace(self, **changes)
