"""The OCR boundary.

Every engine returns the same shape: full text plus per-block bounding boxes.
The boxes are not optional — they produce the evidence crops (FR-13) and the
proportional size check on the government warning. An engine that returns text
alone cannot support the product.

Keeping this a Protocol is what lets the rule engine be tested with no network
and lets the on-prem adapter answer the firewall constraint (C-3) as a config
change rather than a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BoundingBox:
    """Pixel coordinates, origin top-left.

    Providers differ — some return normalised 0..1, some use a different
    origin. Convert at the adapter boundary so nothing downstream has to know.
    """

    x: int
    y: int
    width: int
    height: int

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def right(self) -> int:
        return self.x + self.width


@dataclass(frozen=True)
class TextBlock:
    """One run of text with its position on the image."""

    text: str
    box: BoundingBox
    confidence: float | None = None


@dataclass(frozen=True)
class OcrResult:
    full_text: str
    blocks: tuple[TextBlock, ...]
    image_width: int
    image_height: int
    engine: str
    latency_ms: float

    @property
    def median_text_height(self) -> float:
        """Median block height, used as the baseline for the warning's
        proportional size check. Median rather than mean so one oversized
        brand name does not skew the comparison.
        """
        if not self.blocks:
            return 0.0
        heights = sorted(b.box.height for b in self.blocks)
        mid = len(heights) // 2
        if len(heights) % 2:
            return float(heights[mid])
        return (heights[mid - 1] + heights[mid]) / 2


class OcrEngine(Protocol):
    """Implemented by CloudVisionEngine and FakeOcrEngine.

    A PaddleOcrEngine is the documented on-prem answer to the firewall
    constraint (C-3) and is not written. OCR_ENGINE=paddle raises
    NotImplementedError at startup warming, where it is caught and reported on
    /health as degraded, and again on every check.
    """

    name: str

    def extract(self, image_bytes: bytes) -> OcrResult: ...
