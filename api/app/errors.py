"""Errors that cross the API boundary.

Every one carries a machine-readable code, a sentence saying what happened, and
a sentence saying what to do next. A bare 500 tells an agent nothing, and an
agent who learns nothing rejects the application and stops using the tool
(.claude/rules/error-handling.md).
"""

from __future__ import annotations


class LabelVerificationError(Exception):
    """Base class for failures an agent is expected to read."""

    code = "verification_failed"

    def __init__(self, *, code: str, message: str, what_to_do: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.what_to_do = what_to_do

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "what_to_do": self.what_to_do}


class UnreadableImageError(LabelVerificationError):
    """The image could not be read, for a reason we can name.

    Deliberately not a verdict. "We could not read this" is not "this label is
    non-compliant" — the label may be perfectly compliant and badly photographed,
    and reporting one as the other corrupts every accuracy number we publish
    (PRD FR-3).
    """


class ExtractionError(LabelVerificationError):
    """The field extraction step failed in a way the agent should hear about."""


class StartupError(RuntimeError):
    """A misconfiguration that would otherwise degrade behaviour silently.

    Raised at boot, never during a request. See .claude/rules/error-handling.md.
    """
