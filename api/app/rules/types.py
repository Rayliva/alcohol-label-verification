"""Vocabulary for the compliance engine.

This package is pure: it takes data and returns verdicts. It imports nothing
from `ocr` or `extraction`, which is what keeps it unit-testable with no
network and no mocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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
