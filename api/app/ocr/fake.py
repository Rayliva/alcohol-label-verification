"""Deterministic OCR for tests and credential-free local runs.

This is what lets the stack run without a network. It returns one sample label
whatever the image, so a test that suddenly needs credentials is a signal that
something is reaching past the boundary. Tests that need OCR to track the image
use CorpusOcrEngine instead — see the class docstring below.
"""

from __future__ import annotations

import hashlib

from app.ocr.base import BoundingBox, OcrResult, TextBlock

# A compliant spirits label, used when no fixture matches. Line heights are
# plausible rather than measured — the fake exists for determinism, not realism.
DEFAULT_LINES: tuple[tuple[str, int], ...] = (
    ("OLD TOM DISTILLERY", 76),
    ("Kentucky Straight Bourbon Whiskey", 38),
    ("45% Alc./Vol. (90 Proof)", 30),
    ("750 mL", 30),
    ("Bottled by Old Tom Distillery, Bardstown, Kentucky", 30),
    (
        "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
        "drink alcoholic beverages during pregnancy because of the risk of birth "
        "defects. (2) Consumption of alcoholic beverages impairs your ability to "
        "drive a car or operate machinery, and may cause health problems.",
        18,
    ),
)


def result_from_lines(
    lines: tuple[tuple[str, int], ...],
    *,
    width: int = 1000,
    height: int = 1400,
    engine: str = "fake",
) -> OcrResult:
    """Build an OcrResult from (text, pixel_height) pairs, stacked top to bottom."""
    blocks: list[TextBlock] = []
    y = 150
    for text, text_height in lines:
        blocks.append(
            TextBlock(
                text=text,
                box=BoundingBox(x=70, y=y, width=width - 140, height=text_height),
                confidence=0.99,
            )
        )
        y += text_height + 40
    return OcrResult(
        full_text="\n".join(t for t, _ in lines),
        blocks=tuple(blocks),
        image_width=width,
        image_height=height,
        engine=engine,
        latency_ms=0.0,
    )


class FakeOcrEngine:
    """One compliant sample label, returned for every image.

    Nothing calls `register()` today, so the fixture map is empty and every
    image gets `DEFAULT_LINES` back. That is enough to boot the stack without
    credentials, and it is *not* enough to demonstrate the product: a check run
    this way reports on the sample below rather than on the artwork supplied.
    The README says so under Limitations.

    Tests that need OCR to track the image use `CorpusOcrEngine`
    (`tests/support/corpus.py`), which replays the boxes the corpus renderer
    drew. `register()` is kept for a test that wants to supply its own.
    """

    name = "fake"

    def __init__(self, default: OcrResult | None = None) -> None:
        self._fixtures: dict[str, OcrResult] = {}
        self._default = default or result_from_lines(DEFAULT_LINES)

    @staticmethod
    def key(image_bytes: bytes) -> str:
        return hashlib.sha256(image_bytes).hexdigest()

    def register(self, image_bytes: bytes, result: OcrResult) -> None:
        self._fixtures[self.key(image_bytes)] = result

    def extract(self, image_bytes: bytes) -> OcrResult:
        return self._fixtures.get(self.key(image_bytes), self._default)
