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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.errors import UnreadableImageError
from app.extraction.schema import ExtractedFields
from app.ocr.base import OcrEngine, OcrResult
from app.pipeline import quality
from app.pipeline.measure import crop_box, find_block, measure
from app.rules.engine import Application, LabelObservation, LabelReport, evaluate
from app.rules.types import FieldResult, Verdict, worst

# Pillow only *raises* above twice its own limit; between one and two times it
# warns and proceeds, so a ~200M-pixel PNG well under the upload cap would
# still allocate about a gigabyte on convert. No label needs this many pixels.
Image.MAX_IMAGE_PIXELS = 50_000_000

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

# Above this, every stage that touches pixels is paying for resolution no part
# of the check can use. Measured on the deployed instance, 2026-08-11: the same
# label at 1372x1852 and at 4116x5556 came back in 2.7 s and 9.3 s. The extra
# 6.6 s was entirely image work - the quality gate went 302 ms to 2,923 ms and
# geometric measurement 299 ms to 2,602 ms - and it bought nothing, because the
# text was legible at both sizes.
#
# 2400 is chosen to sit above the corpus rather than inside it: the largest
# curated label is 2000 px on its long edge and the largest sample is 1932, so
# every image any threshold was calibrated against passes through untouched.
# Only photographs bigger than anything we have ever measured are resampled.
MAX_WORKING_EDGE = 2400

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


def _decode(image_bytes: bytes) -> tuple[Image.Image, bytes]:
    """Open an upload as an upright RGB image, or say why it could not be.

    Returns the image and the bytes the OCR engine should be given, which are
    the original bytes unless the photograph was resampled.

    Three failures reach this function from real submissions and none of them
    may become a bare 500: a file that is not an image at all, a file that is
    truncated in transit, and a small file declaring enormous dimensions.
    """
    if image_bytes[:5] == b"%PDF-":
        raise UnreadableImageError(
            code="unsupported_file",
            message="This is a PDF. The tool reads label artwork as an image.",
            what_to_do="Export the label artwork as a JPG or PNG and upload that.",
        )
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except UnidentifiedImageError as exc:
        raise UnreadableImageError(
            code="unsupported_file",
            message="This file could not be opened as an image.",
            what_to_do="Upload the label artwork as a JPG or PNG.",
        ) from exc
    except Image.DecompressionBombError as exc:
        raise UnreadableImageError(
            code="image_dimensions_implausible",
            message="This file claims dimensions far larger than any label photograph.",
            what_to_do="Re-export the artwork at a normal size and upload it again.",
        ) from exc
    except OSError as exc:
        raise UnreadableImageError(
            code="image_truncated",
            message="The image file is incomplete. It ends part way through.",
            what_to_do="Upload the file again; it may have been cut short in transit.",
        ) from exc

    # Every phone writes portrait shots as landscape pixels plus an orientation
    # tag. Ignoring it hands the agent sideways evidence crops and makes a
    # one-panel label look like a two-panel container to the field-of-vision
    # check.
    upright = ImageOps.exif_transpose(image).convert("RGB")

    if max(upright.size) <= MAX_WORKING_EDGE:
        return upright, image_bytes

    # Resampled once, here, so that every stage downstream - the quality gate,
    # OCR, geometric measurement, the crops - sees the same pixels. Measuring
    # focus on the image OCR actually reads is also the more honest question:
    # a blur that vanishes under resampling was never obscuring the text.
    scale = MAX_WORKING_EDGE / max(upright.size)
    working = upright.resize(
        (max(1, round(upright.width * scale)), max(1, round(upright.height * scale))),
        Image.Resampling.LANCZOS,
    )
    buffer = BytesIO()
    working.save(buffer, format="JPEG", quality=92)
    return working, buffer.getvalue()


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
        if region is None:
            missing.append(name)
            continue
        region.thumbnail((MAX_CROP_EDGE, MAX_CROP_EDGE))
        buffer = BytesIO()
        # PNG, because an agent is looking at this crop to decide whether we
        # misread the label, and JPEG ringing around small type is exactly the
        # artefact that would make them doubt a correct reading. Not optimised:
        # measured over seven crops, optimize=True cost 48 ms against 13 ms and
        # saved about a kilobyte each.
        region.save(buffer, format="PNG")
        crops[name] = buffer.getvalue()
    return crops, tuple(missing)


# Below this, the text behind a field was not read well enough to decide
# anything on. Measured over the sample set with Cloud Vision: a clean label's
# worst block reads 0.94-0.96, while degraded ones carry blocks at 0.54 and
# 0.61. 0.85 sits in that gap with room on both sides.
MIN_READ_CONFIDENCE = 0.85


def temper_by_reading(results: Sequence[FieldResult], ocr: OcrResult) -> list[FieldResult]:
    """Downgrade verdicts whose evidence was barely legible.

    A verdict means the check ran. If the text it ran against was a guess, the
    honest answer is that a person should look — not a confident FAIL, which
    accuses a compliant label, and not a confident PASS, which is worse still
    because a false PASS is the error this tool exists to prevent.

    Only fields with text to doubt are touched. Whether an *absent* field is a
    violation is the matcher's business, not this function's.
    """
    tempered: list[FieldResult] = []
    for result in results:
        block = find_block(ocr, result.detected) if result.detected else None
        confidence = block.confidence if block else None
        if (
            confidence is None
            or confidence >= MIN_READ_CONFIDENCE
            or result.verdict is Verdict.NEEDS_REVIEW
        ):
            tempered.append(result)
            continue
        tempered.append(
            replace(
                result,
                verdict=Verdict.NEEDS_REVIEW,
                reason=(
                    f"{result.reason} This text could not be read confidently "
                    f"({confidence:.0%}), so the finding may be about the "
                    "photograph rather than the label, so compare it against the "
                    "artwork before deciding."
                ),
            )
        )
    return tempered


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
    image, ocr_bytes = _decode(image_bytes)
    decode_ms = (time.perf_counter() - mark) * 1000

    mark = time.perf_counter()
    quality.require_readable(image)
    quality_ms = (time.perf_counter() - mark) * 1000

    mark = time.perf_counter()
    ocr_result = ocr.extract(ocr_bytes)
    ocr_ms = (time.perf_counter() - mark) * 1000

    quality.require_text(ocr_result)

    mark = time.perf_counter()
    detected = _detected_fields(extract(ocr_result.full_text))
    extraction_ms = (time.perf_counter() - mark) * 1000

    mark = time.perf_counter()
    layout = measure(image, ocr_result, detected)
    report = evaluate(application, LabelObservation(fields=detected, layout=layout))
    # The rule engine judges text; it has no idea how well that text was read.
    # Temper its verdicts here, where the OCR result is still in hand, and
    # recompute the roll-up so the headline follows the tempered fields.
    tempered = tuple(temper_by_reading(report.fields, ocr_result))
    if tempered != report.fields:
        report = replace(
            report,
            fields=tempered,
            overall=worst(
                [f.verdict for f in tempered] + [c.verdict for c in report.warning_checks]
            ),
            counts={
                verdict: sum(1 for f in tempered if f.verdict is verdict) for verdict in Verdict
            },
        )
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
