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

Focus and exposure are separate faults. Measuring sharpness on the raw image
conflates them — dimming a photograph scales its high-frequency energy down
without moving a single edge — so focus is scaled by the image's white point
and exposure is judged on its own. Reporting the wrong one sends an agent to
re-shoot for the wrong reason.

Thresholds were measured against tier 4 of the corpus, which is half
degraded-but-readable and half unreadable by construction, and against tiers
1-3 and 5 to confirm they do not fire on labels that are fine. The numbers and
the method are recorded in docs/specs/pipeline.md 2.1, along with one figure
that is not reproducible here and a known limitation of the measure.

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

# Focus, normalised for exposure so a dark photograph is not mistaken for a
# soft one. Dimming scales high-frequency energy down with everything else, so
# the raw measure reported sharp-but-underexposed labels as blurry — sending an
# agent to re-shoot for focus when they needed to turn on a light.
#
# Reproducible on corpus/out (see tests/unit/test_quality.py for the synthetic
# cases): t4-blur-heavy 0.07, t4-blur-light 5.19, t4-low-light 15.62,
# t1-clean-classic-1 15.57. 2.9 is the geometric midpoint of 1.90 — the worst
# frame that must be refused — and 4.31, the worst that must still be read.
# That 4.31 is from an external label set not committed here; on committed data
# alone the worst must-read is t4-blur-light at 5.19, and sqrt(1.90 x 5.19) is
# 3.14, so the threshold holds either way. docs/specs/pipeline.md 2.1 records a
# known limitation: blurred + dim + noisy frames can land on either side.
MIN_FOCUS = 2.9

# Above this, with the overall contrast to match, the frame is sensor noise
# rather than detail. Clean labels top out near 20.
MAX_HIGH_FREQUENCY = 25.0
NOISE_CONTRAST = 50.0

# Underexposed past recovery. A deliberately dark label design sits near 28
# mean with 30 contrast, so both conditions are required.
MIN_MEAN_LUMINANCE = 30.0
MIN_CONTRAST = 10.0

# Ink running off the edge of the frame means content was cut off.
#
# The band is a fraction of the long edge, not a pixel count. "At the very edge
# of the frame" is a question about proportion, and a fixed 6 px band answered
# it differently at every resolution: on a 4116 px photograph 6 px is 0.15% of
# the frame, and on a 560 px one it is 1.1%. That became a live false FAIL once
# oversized photographs were resampled, because a border printed 10 px inside a
# 4116 px frame lands 6 px inside a 2400 px one, and the same intact label went
# from 0.00 to 0.33 border ink and was rejected as cropped.
#
# 0.006 reproduces the old 6 px at the ~1000 px the corpus renders at. Measured
# across all 95 curated and sample labels on 2026-08-11: identical outcomes,
# same two images over the threshold, no verdict moved.
BORDER_BAND_FRACTION = 0.006
MIN_BORDER_BAND_PX = 2
MAX_BORDER_INK = 0.05

# OCR that comes back this unsure has not read the label.
MIN_MEAN_OCR_CONFIDENCE = 0.45
MIN_TEXT_CHARACTERS = 40


@dataclass(frozen=True)
class ImageQuality:
    """Everything measured about the image itself, before any text is read."""

    width: int
    height: int
    high_frequency: float
    focus: float
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
    band = max(MIN_BORDER_BAND_PX, round(max(width, height) * BORDER_BAND_FRACTION))
    edges = [
        grey.crop((0, 0, width, band)),
        grey.crop((0, height - band, width, height)),
        grey.crop((0, 0, band, height)),
        grey.crop((width - band, 0, width, height)),
    ]
    inked = 0
    total = 0
    for edge in edges:
        # Each edge is measured against its own most common tone, not against
        # one shared corner. A full-bleed dark band along one side is an
        # ordinary label design; measuring the other three edges against a patch
        # inside that band scored all three as ink and called an intact label
        # cropped.
        histogram = edge.histogram()
        reference = max(range(len(histogram)), key=lambda value: histogram[value])
        marks = edge.point(lambda v, ref=reference: 255 if abs(v - ref) > 60 else 0).histogram()
        inked += marks[255]
        total += marks[0] + marks[255]
    return inked / total if total else 0.0


def _white_point(grey: Image.Image, ignore_fraction: float = 0.01) -> int:
    """The luminance the brightest 1% of pixels sit at or above.

    Underexposure scales the whole signal, and the white point scales with it,
    so dividing by it removes the exposure term from a sharpness measure.

    Normalising by the full min-to-max range instead — what `autocontrast`
    does — looks equivalent and is not: that range collapses on any *low
    contrast* image whatever its exposure, handing enormous gain to sensor
    noise and scoring a badly blurred photograph as sharp.
    """
    histogram = grey.histogram()
    total = sum(histogram)
    seen = 0
    for value in range(255, -1, -1):
        seen += histogram[value]
        if seen >= total * ignore_fraction:
            return max(value, 1)
    return 255


def assess(image: Image.Image) -> ImageQuality:
    """Measure the image. No judgement here — see `require_readable`."""
    grey = image.convert("L")
    blurred = grey.filter(ImageFilter.GaussianBlur(2))
    statistics = ImageStat.Stat(grey)
    # Speckle removed before focus is measured: a median filter takes out
    # isolated noisy pixels while leaving real edges, so sensor grain cannot be
    # counted as detail. Then scaled by the white point (below).
    denoised = grey.filter(ImageFilter.MedianFilter(3))
    denoised_edges = ImageChops.difference(denoised, denoised.filter(ImageFilter.GaussianBlur(2)))
    return ImageQuality(
        width=image.width,
        height=image.height,
        high_frequency=ImageStat.Stat(ImageChops.difference(grey, blurred)).stddev[0],
        focus=ImageStat.Stat(denoised_edges).stddev[0] * 255.0 / _white_point(denoised),
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

    if quality.focus < MIN_FOCUS:
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

# Known limitation: artwork printed on pure white paper leaves no luminance
# headroom above the background, so a reflection is indistinguishable from paper
# by this measure. Such an image falls through to the OCR checks and is reported
# unreadable for a different reason. Published in the README rather than papered
# over — see .claude/rules/measure-dont-claim.md.


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

    # Glare is light brighter than the label's own background. On stock this
    # pale there is no headroom left to be brighter in, so it cannot be seen —
    # and the README records that as a limitation.
    #
    # This used to clamp to 255 instead, to stop the check becoming dead code.
    # That made it worse than dead. A blank margin has mean 255 and no
    # variation, which satisfies both washed-strip conditions, so a label that
    # simply *omitted its government warning* was reported as a reflection and
    # never checked — the violation hidden behind a complaint about the
    # photograph, which is the inversion this module exists to prevent.
    if background + GLARE_ABOVE_BACKGROUND > 255.0:
        return

    threshold = max(GLARE_MIN_LUMINANCE, background + GLARE_ABOVE_BACKGROUND)

    washed_strips = []
    for index in range(GLARE_STRIPS // 2, GLARE_STRIPS):
        top = index * strip_height
        strip = grey.crop((0, top, grey.width, min(grey.height, top + strip_height)))
        statistics = ImageStat.Stat(strip)
        washed_strips.append(
            statistics.mean[0] >= threshold and statistics.stddev[0] <= GLARE_MAX_CONTRAST
        )

    # The washed run has to reach the bottom of the frame. A reflection over the
    # lower part of a bottle covers the bottom edge; the empty margin between
    # the bottler line and the warning does not, and that margin is flat and
    # bright on any pale label.
    trailing = 0
    for washed in reversed(washed_strips):
        if not washed:
            break
        trailing += 1

    if trailing >= GLARE_MIN_STRIPS:
        covered = round(trailing / GLARE_STRIPS * 100)
        raise UnreadableImageError(
            code="glare_obscures_text",
            message=(
                f"A bright reflection covers roughly the lower {covered}% of the label, "
                "including where the government warning would be."
            ),
            what_to_do="Re-photograph the bottle without direct light falling on it.",
        )
