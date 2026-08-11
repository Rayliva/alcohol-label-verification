"""Engine selection, driven by OCR_ENGINE.

The seam exists so that `OCR_ENGINE=paddle` — the documented answer to TTB's
firewall (C-3) — is one adapter away rather than a rewrite. That adapter is not
written: selecting it raises below. See .claude/skills/swap-ocr-engine.md
"""

from __future__ import annotations

from functools import cache

from app.config import settings
from app.ocr.base import OcrEngine


@cache
def get_engine(name: str | None = None) -> OcrEngine:
    """Return the configured OCR engine. Cached — clients are expensive to build."""
    engine = (name or settings.ocr_engine).lower()

    if engine == "fake":
        from app.ocr.fake import FakeOcrEngine

        return FakeOcrEngine()

    if engine == "cloud":
        from app.ocr.cloud_vision import CloudVisionEngine

        return CloudVisionEngine()

    if engine == "paddle":
        raise NotImplementedError(
            "The PaddleOCR adapter is not implemented yet (PRD P2). "
            "Use OCR_ENGINE=cloud or OCR_ENGINE=fake."
        )

    raise ValueError(f"Unknown OCR_ENGINE {engine!r}. Expected one of: cloud, paddle, fake.")
