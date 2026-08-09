"""Is this image readable, and if not, exactly why?

An agent who gets "processing failed" learns nothing, rejects the application,
and concludes the tool wastes their time. That is Dave Morrison's objection, and
it is the reason every failure here carries a cause and a remedy
(.claude/rules/error-handling.md, PRD FR-15).

**Unreadable is not FAIL.** A compliant label photographed badly is not a
violation. The two outcomes stay in separate buckets everywhere (PRD FR-3).

Two passes. Image statistics before OCR — resolution, focus, exposure, noise,
glare, whether the label runs off the frame — then the OCR result itself,
which is the strongest evidence available about whether text could be read.

Thresholds were measured against tier 4 of the corpus, which is half
degraded-but-readable and half unreadable by construction, and against tiers 1-3
and 5 to confirm they do not fire on labels that are fine. The numbers are
recorded in docs/specs/pipeline.md and re-derived by
`python -m app.pipeline.quality --calibrate`.

See docs/specs/pipeline.md 2.1
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageChops, ImageFilter, ImageStat

from app.errors import UnreadableImageError
from app.ocr.base import OcrResult

# A label narrower than this cannot carry legible warning text at any
# reasonable print size. Measured: the corpus renders at 1000 px; the
# downscaled-but-readable variant survives at 770.
MIN_LONG_EDGE = 700

# High-frequency energy: the standard deviation of (image - blurred image).
# Sharp text scores 15-20 on this corpus, a light focus miss 5.4, and an image
# blurred past recovery 0.07.
MIN_HIGH_FREQUENCY = 3.0

# Above this, with the overall contrast to match, the frame is sensor noise
# rather than detail. Clean labels top out near 20.
MAX_HIGH_FREQUENCY = 25.0
NOISE_CONTRAST = 50.0

# Underexposed past recovery. A deliberately dark label design sits near 28
# mean with 30 contrast, so both conditions are required.
MIN_MEAN_LUMINANCE = 30.0
MIN_CONTRAST = 10.0

# Ink running off the edge of the frame means content was cut off.
BORDER_BAND_PX = 6
MAX_BORDER_INK = 0.12

# OCR that comes back this unsure has not read the label.
MIN_MEAN_OCR_CONFIDENCE = 0.45
MIN_TEXT_CHARACTERS = 40


@dataclass(frozen=True)
class ImageQuality:
    """Everything measured about the image itself, before any text is read."""

    width: int
    height: int
    high_frequency: float
    mean_luminance: float
    contrast: float
    border_ink: float

    @property
    def long_edge(self) -> int:
        return max(self.width, self.height)


def _border_ink_fraction(grey: Image.Image) -> float:
    """How much of the outermost band differs from the frame's own margin.

    A label photographed whole has quiet margins. Content running off the edge
    means the frame cut through the label.
    """
    width, height = grey.size
    band = BORDER_BAND_PX
    edges = [
        grey.crop((0, 0, width, band)),
        grey.crop((0, height - band, width, height)),
        grey.crop((0, 0, band, height)),
        grey.crop((width - band, 0, width, height)),
    ]
    corner = ImageStat.Stat(grey.crop((0, 0, band, band))).mean[0]
    inked = 0
    total = 0
    for edge in edges:
        histogram = (
            edge.convert("L").point(lambda v: 255 if abs(v - corner) > 60 else 0).histogram()
        )
        inked += histogram[255]
        total += histogram[0] + histogram[255]
    return inked / total if total else 0.0


def assess(image: Image.Image) -> ImageQuality:
    """Measure the image. No judgement here — see `require_readable`."""
    grey = image.convert("L")
    blurred = grey.filter(ImageFilter.GaussianBlur(2))
    statistics = ImageStat.Stat(grey)
    return ImageQuality(
        width=image.width,
        height=image.height,
        high_frequency=ImageStat.Stat(ImageChops.difference(grey, blurred)).stddev[0],
        mean_luminance=statistics.mean[0],
        contrast=statistics.stddev[0],
        border_ink=_border_ink_fraction(grey),
    )


def require_readable(image: Image.Image) -> ImageQuality:
    """Raise UnreadableImageError if the image cannot be read, naming the cause."""
    quality = assess(image)

    if quality.long_edge < MIN_LONG_EDGE:
        raise UnreadableImageError(
            code="image_too_small",
            message=(
                f"This image is {quality.width} by {quality.height} pixels. Label text "
                "at that size cannot be read reliably."
            ),
            what_to_do=f"Send a photo at least {MIN_LONG_EDGE} pixels on its long edge.",
        )

    if quality.mean_luminance < MIN_MEAN_LUMINANCE and quality.contrast < MIN_CONTRAST:
        raise UnreadableImageError(
            code="image_too_dark",
            message="The photograph is too dark to make out any text on the label.",
            what_to_do="Re-photograph the bottle in better light, without a flash on the glass.",
        )

    if quality.high_frequency < MIN_HIGH_FREQUENCY:
        raise UnreadableImageError(
            code="image_too_blurry",
            message="The image is too blurry to read the text on the label.",
            what_to_do="A sharper photo from the same angle and distance should work.",
        )

    if quality.high_frequency > MAX_HIGH_FREQUENCY and quality.contrast > NOISE_CONTRAST:
        raise UnreadableImageError(
            code="image_too_noisy",
            message="Picture noise is covering the text on the label.",
            what_to_do="Re-photograph in brighter light, which lets the camera use less gain.",
        )

    require_no_glare(image)

    if quality.border_ink > MAX_BORDER_INK:
        raise UnreadableImageError(
            code="label_cropped",
            message=(
                "The label appears to run off the edge of the frame, so part of it is "
                "missing. The government warning may be outside the picture."
            ),
            what_to_do="Re-photograph with the whole label inside the frame.",
        )

    return quality


def require_text(ocr: OcrResult) -> None:
    """Raise if OCR came back with nothing usable, naming the cause.

    The OCR result is the strongest evidence available about whether the label
    could be read, which is why the second pass happens here rather than in a
    cleverer image statistic.
    """
    text = ocr.full_text.strip()
    if not text:
        raise UnreadableImageError(
            code="no_text_found",
            message="No text could be read anywhere on this image.",
            what_to_do=(
                "Check that the file is a photograph of a label, then re-send it "
                "sharper and better lit."
            ),
        )

    confidences = [b.confidence for b in ocr.blocks if b.confidence is not None]
    if confidences and sum(confidences) / len(confidences) < MIN_MEAN_OCR_CONFIDENCE:
        raise UnreadableImageError(
            code="text_unreadable",
            message="Text is visible on the label but could not be read with any confidence.",
            what_to_do="A sharper, straighter photograph of the same label should work.",
        )

    if len(text) < MIN_TEXT_CHARACTERS:
        raise UnreadableImageError(
            code="text_unreadable",
            message=(
                f"Only {len(text)} characters could be read from this label, far less "
                "than a label carries."
            ),
            what_to_do="A sharper, straighter photograph of the same label should work.",
        )


# A washed-out band is only evidence of glare when it is brighter than the
# label's own background. An empty margin is flat too, and reporting a label
# that simply omits its warning as "glare" would hide the violation behind an
# image problem — the exact inversion this product cannot afford.
GLARE_STRIPS = 10
GLARE_MIN_STRIPS = 2
GLARE_MIN_LUMINANCE = 250.0
GLARE_ABOVE_BACKGROUND = 3.0
GLARE_MAX_CONTRAST = 4.0


def _background_luminance(grey: Image.Image) -> float:
    """The most common tone in the image: the label's own paper."""
    histogram = grey.histogram()
    return float(max(range(len(histogram)), key=lambda value: histogram[value]))


def require_no_glare(image: Image.Image) -> None:
    """Report a reflection washing out the lower part of the label.

    Glare over the bottom of a bottle is the common case, and the bottom is
    where the government warning lives. Saying "a reflection covers the lower
    third" is the difference between an agent re-photographing a bottle and an
    agent rejecting a compliant application.
    """
    grey = image.convert("L")
    background = _background_luminance(grey)
    strip_height = max(1, grey.height // GLARE_STRIPS)

    run = 0
    longest = 0
    for index in range(GLARE_STRIPS // 2, GLARE_STRIPS):
        top = index * strip_height
        strip = grey.crop((0, top, grey.width, min(grey.height, top + strip_height)))
        statistics = ImageStat.Stat(strip)
        washed = (
            statistics.mean[0] >= max(GLARE_MIN_LUMINANCE, background + GLARE_ABOVE_BACKGROUND)
            and statistics.stddev[0] <= GLARE_MAX_CONTRAST
        )
        run = run + 1 if washed else 0
        longest = max(longest, run)

    if longest >= GLARE_MIN_STRIPS:
        covered = round(longest / GLARE_STRIPS * 100)
        raise UnreadableImageError(
            code="glare_obscures_text",
            message=(
                f"A bright reflection covers roughly the lower {covered}% of the label, "
                "including where the government warning would be."
            ),
            what_to_do="Re-photograph the bottle without direct light falling on it.",
        )
