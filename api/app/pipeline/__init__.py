"""The verification pipeline: pixels in, verdicts out.

This is the only package that touches images. Everything below it — the rule
engine — sees data. See docs/specs/pipeline.md
"""

from __future__ import annotations

from app.pipeline.run import StageTimings, VerificationResult, verify

__all__ = ["StageTimings", "VerificationResult", "verify"]
