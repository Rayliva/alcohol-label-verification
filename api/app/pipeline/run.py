"""The verification pipeline.

image bytes -> quality gate -> OCR -> extraction -> measurement -> rules -> crops

The vision model is not on this path. The extraction call sees OCR text, never
pixels, which is what keeps a label inside the five-second budget the brief is
most emphatic about (tech-spec → Architecture, PRD NFR-1).

`ocr` and `extract` are injected. They are the two boundaries this system has,
and they are the only two things a test mocks
(.claude/rules/test-driven-development.md).

See docs/specs/pipeline.md 2.4
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.errors import UnreadableImageError
from app.extraction.schema import ExtractedFields
from app.ocr.base import OcrEngine, OcrResult
from app.pipeline import quality
from app.pipeline.measure import crop_box, find_block, measure
from app.rules.engine import Application, LabelObservation, LabelReport, evaluate

# Fields the rule engine knows, in the order the extraction schema supplies them.
EXTRACTED_FIELDS = (
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_address",
    "country_of_origin",
    "government_warning",
)

# An evidence crop is read at a glance beside the declared value, not zoomed
# into. Capping it keeps a 200-label batch from carrying 200 full photographs.
MAX_CROP_EDGE = 900

Extractor = Callable[[str], ExtractedFields]


@dataclass(frozen=True)
class StageTimings:
    """Milliseconds per stage. NFR-1 requires published numbers."""

    decode_ms: float = 0.0
    quality_ms: float = 0.0
    ocr_ms: float = 0.0
    extraction_ms: float = 0.0
    rules_ms: float = 0.0
    crops_ms: float = 0.0
    total_ms: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "decode_ms": round(self.decode_ms, 1),
            "quality_ms": round(self.quality_ms, 1),
            "ocr_ms": round(self.ocr_ms, 1),
            "extraction_ms": round(self.extraction_ms, 1),
            "rules_ms": round(self.rules_ms, 1),
            "crops_ms": round(self.crops_ms, 1),
            "total_ms": round(self.total_ms, 1),
        }


@dataclass(frozen=True)
class VerificationResult:
    """One label, checked."""

    report: LabelReport
    detected: Mapping[str, str | None]
    crops: Mapping[str, bytes]
    timings: StageTimings
    ocr_engine: str
    crops_missing: tuple[str, ...] = field(default_factory=tuple)


def _decode(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except UnidentifiedImageError as exc:
        raise UnreadableImageError(
            code="unsupported_file",
            message="This file could not be opened as an image.",
            what_to_do="Upload the label artwork as a JPG or PNG.",
        ) from exc
    return image.convert("RGB")


def _detected_fields(fields: ExtractedFields) -> dict[str, str | None]:
    return {name: getattr(fields, name) for name in EXTRACTED_FIELDS}


def _crops(
    image: Image.Image, ocr: OcrResult, detected: Mapping[str, str | None]
) -> tuple[dict[str, bytes], tuple[str, ...]]:
    """One PNG per field, plus the fields that have no region to show.

    A field absent from the label has no crop, and the UI keeps the panel with
    "Not found anywhere on the label" rather than collapsing the row
    (docs/ui-spec.md resolution 3).
    """
    crops: dict[str, bytes] = {}
    missing: list[str] = []
    for name, value in detected.items():
        if not value:
            missing.append(name)
            continue
        block = find_block(ocr, value)
        if block is None:
            missing.append(name)
            continue
        region = crop_box(image, block.box)
        region.thumbnail((MAX_CROP_EDGE, MAX_CROP_EDGE))
        buffer = BytesIO()
        region.save(buffer, format="PNG", optimize=True)
        crops[name] = buffer.getvalue()
    return crops, tuple(missing)


def verify(
    image_bytes: bytes,
    application: Application,
    *,
    ocr: OcrEngine,
    extract: Extractor,
) -> VerificationResult:
    """Check one label against one application.

    Raises UnreadableImageError, with a code and a remedy, when the image cannot
    be read. It never raises for a readable label: a check that cannot run comes
    back NEEDS_REVIEW, because a verdict means the check ran.
    """
    started = time.perf_counter()

    mark = time.perf_counter()
    image = _decode(image_bytes)
    decode_ms = (time.perf_counter() - mark) * 1000

    mark = time.perf_counter()
    quality.require_readable(image)
    quality_ms = (time.perf_counter() - mark) * 1000

    mark = time.perf_counter()
    ocr_result = ocr.extract(image_bytes)
    ocr_ms = (time.perf_counter() - mark) * 1000

    quality.require_text(ocr_result)

    mark = time.perf_counter()
    detected = _detected_fields(extract(ocr_result.full_text))
    extraction_ms = (time.perf_counter() - mark) * 1000

    mark = time.perf_counter()
    layout = measure(image, ocr_result, detected)
    report = evaluate(application, LabelObservation(fields=detected, layout=layout))
    rules_ms = (time.perf_counter() - mark) * 1000

    mark = time.perf_counter()
    crops, missing = _crops(image, ocr_result, detected)
    crops_ms = (time.perf_counter() - mark) * 1000

    return VerificationResult(
        report=report,
        detected=detected,
        crops=crops,
        crops_missing=missing,
        ocr_engine=ocr_result.engine,
        timings=StageTimings(
            decode_ms=decode_ms,
            quality_ms=quality_ms,
            ocr_ms=ocr_ms,
            extraction_ms=extraction_ms,
            rules_ms=rules_ms,
            crops_ms=crops_ms,
            total_ms=(time.perf_counter() - started) * 1000,
        ),
    )
