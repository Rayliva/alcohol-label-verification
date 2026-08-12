"""The wire format, exactly as docs/ui-spec.md → Data shape defines it.

Pydantic models rather than dicts so the shape is checked at the boundary and
the OpenAPI document the frontend reads stays honest.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Outcome = Literal["pass", "needs_review", "fail", "unreadable"]


class ErrorBody(BaseModel):
    """Every failure an agent reads: what happened, and what to do next."""

    code: str = Field(description="Machine-readable cause, e.g. glare_obscures_text")
    message: str = Field(description="What went wrong, in plain words")
    what_to_do: str = Field(description="The next action that would fix it")
    partial_fields_shown: bool = False


class FieldOutcome(BaseModel):
    field: str
    display_name: str
    declared: str | None
    detected: str | None
    verdict: Literal["pass", "needs_review", "fail"]
    confidence: float
    reason: str
    # A data URI rather than a path: there is no storage in this service, so a
    # crop has nowhere to live between requests (PRD C-2). Null when the field
    # was not found on the label — that panel keeps its size and says so
    # (ui-spec resolution 3).
    crop_url: str | None = None
    citation: str | None = None
    override: None = None


class WarningSubCheck(BaseModel):
    check: str
    display_name: str
    verdict: Literal["pass", "needs_review", "fail"]
    reason: str


class VerificationResponse(BaseModel):
    """One label, checked. Mirrors ui-spec → Data shape."""

    label_id: str | None = None
    # The queue row this upload became, so the client can record a decision
    # against it without a trip through the queue. None on recorded seeded
    # results, which already live in the queue under their own id.
    queue_id: str | None = None
    beverage_type: str
    overall: Outcome
    processing_ms: int
    reviewer: str | None = None
    error: ErrorBody | None = None
    fields: list[FieldOutcome] = Field(default_factory=list)
    warning_checks: list[WarningSubCheck] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    stage_ms: dict[str, float] = Field(default_factory=dict)
    ocr_engine: str | None = None


class BeverageTypeOption(BaseModel):
    """One choice on the beverage-type selector.

    `available: false` ships with a reason, because a disabled control that
    does not explain itself is a dead end (.claude/rules/accessibility.md 9).
    """

    beverage_type: str
    display_name: str
    citation: str
    available: bool
    unavailable_reason: str | None = None
    alcohol_content_required: bool
    alcohol_content_note: str | None = None
