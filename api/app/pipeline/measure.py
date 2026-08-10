"""Geometric facts, measured from the image so the rule engine never sees pixels.

Everything here is a **proxy**. 27 CFR 16.22 states absolute type sizes in
millimetres and requires the prefix to be bold and the statement to contrast
with its background; none of those is derivable from an uncalibrated photograph.
What is derivable is the warning's size relative to the text around it, the ink
density of the prefix relative to the rest of the statement, and the luminance
separation inside the warning region. Those catch the abuse pattern that
actually occurs (PRD OS-7), and they are published as proxies rather than
presented as measurements of the regulatory quantity.

Any measurement that cannot be taken comes back None, and the rule engine turns
that into NEEDS_REVIEW rather than PASS.

See docs/specs/pipeline.md 2.2
"""

from __future__ import annotations

import math

from PIL import Image

from app.ocr.base import BoundingBox, OcrResult, TextBlock
from app.rules.types import LayoutMetrics
from app.rules.warning import STATUTORY_WARNING, WARNING_PREFIX

# OCR engines return blocks at different granularities: a word, a line, or a
# whole paragraph. Comparing a paragraph's box height against a single line's
# would report the warning as several times the size of the brand name.
#
# For a block of N characters in a box W wide and H tall, laid out in L lines of
# height h, W is about (N/L) * 0.5h and H is about L*h. Eliminating L gives
# h = sqrt(2HW/N) — which collapses to exactly H for a single-line block, so one
# estimator covers both cases.
_GLYPH_ASPECT = 0.5

# Beyond this the picture is wide enough to be two panels of a container
# photographed side by side, which is what the field-of-vision check needs.
PANEL_ASPECT_RATIO = 1.25

# A field that is not on the label has no side. Distinct from a field whose
# position could not be established, which is a measurement failure.
ABSENT = "absent"


def estimated_line_height(block: TextBlock) -> float:
    """The height of one line of text inside a block, whatever its granularity."""
    characters = len(block.text.strip())
    if characters <= 0 or block.box.height <= 0 or block.box.width <= 0:
        return float(block.box.height)
    estimate = math.sqrt(block.box.height * block.box.width / (characters * _GLYPH_ASPECT))
    return min(float(block.box.height), estimate)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def warning_blocks(ocr: OcrResult) -> list[TextBlock]:
    """Blocks that carry the government warning."""
    return [b for b in ocr.blocks if WARNING_PREFIX in b.text.upper()]


def _warning_statement_blocks(ocr: OcrResult) -> list[TextBlock]:
    """Every block that is part of the government warning, not just its first line.

    A block belongs to the statement if it carries the prefix, or if its text
    appears inside the statutory wording. Matching against the statute rather
    than against geometry means a wrapped warning is recognised whatever block
    granularity the OCR engine happens to return.
    """
    statute = " ".join(STATUTORY_WARNING.split()).casefold()
    belongs = []
    for block in ocr.blocks:
        text = " ".join(block.text.split()).casefold()
        if not text:
            continue
        if WARNING_PREFIX in block.text.upper() or (len(text) > 8 and text in statute):
            belongs.append(block)
    return belongs


def _relative_luminance(grey_value: float) -> float:
    """WCAG relative luminance from an 8-bit grey level."""
    channel = grey_value / 255
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _percentile(histogram: list[int], fraction: float) -> float:
    total = sum(histogram)
    if not total:
        return 0.0
    target = total * fraction
    running = 0
    for value, count in enumerate(histogram):
        running += count
        if running >= target:
            return float(value)
    return 255.0


def contrast_ratio(region: Image.Image) -> float | None:
    """WCAG contrast between the darkest and lightest tones present."""
    grey = region.convert("L")
    if grey.width < 4 or grey.height < 4:
        return None
    histogram = grey.histogram()
    dark = _relative_luminance(_percentile(histogram, 0.05))
    light = _relative_luminance(_percentile(histogram, 0.95))
    lighter, darker = max(dark, light), min(dark, light)
    return (lighter + 0.05) / (darker + 0.05)


def mean_stroke_width(
    region: Image.Image, threshold: float, ink_is_dark: bool = True
) -> float | None:
    """Average width of an inked run, scanning row by row.

    Ink *density* was the obvious measure and it does not work: GOVERNMENT
    WARNING is uppercase and the sentence beside it is not, so capitals alone
    push density up by roughly as much as bold does. Measured on the corpus, the
    bold and unbold variants came back 1.37 and 1.15 — indistinguishable.

    Run length is a direct estimate of stroke thickness and is far less
    sensitive to which letters happen to be present.

    `ink_is_dark` exists because a label can be light type on a dark ground.
    Assuming ink is always the darker tone measures the background on those
    labels and reports a compliant warning as unbold.
    """
    grey = region.convert("L")
    if grey.width < 2 or grey.height < 2:
        return None
    pixels = grey.load()
    if pixels is None:
        return None
    inked = 0
    runs = 0
    cutoff = int(threshold)
    for y in range(grey.height):
        in_run = False
        for x in range(grey.width):
            value = pixels[x, y]
            if (value <= cutoff) if ink_is_dark else (value >= cutoff):
                inked += 1
                if not in_run:
                    runs += 1
                    in_run = True
            else:
                in_run = False
    if runs < 4:
        return None
    return inked / runs


def _prefix_stroke_ratio(image: Image.Image, block: TextBlock, line_height: float) -> float | None:
    """Stroke thickness of GOVERNMENT WARNING against the rest of its own line.

    Comparing the prefix against the statement printed beside it holds size,
    typeface and print quality constant, so what is left is weight. It is a
    proxy, calibrated against the corpus rather than assumed — see the README.
    """
    box = block.box
    if line_height <= 2 or box.width <= 0:
        return None

    left = max(0, min(image.width, box.x))
    top = max(0, min(image.height, box.y))
    right = max(left, min(image.width, box.right))
    bottom = max(top, min(image.height, box.y + int(line_height * 1.4), box.bottom))
    if right - left < 20 or bottom - top < 4:
        return None
    line = image.crop((left, top, right, bottom))

    histogram = line.convert("L").histogram()
    threshold = (_percentile(histogram, 0.05) + _percentile(histogram, 0.95)) / 2
    # Ink is whichever tone is in the minority: text covers less of a line than
    # the ground it sits on.
    below = sum(histogram[: int(threshold) + 1])
    ink_is_dark = below <= sum(histogram) - below

    prefix_width = int(len(WARNING_PREFIX) * _GLYPH_ASPECT * line_height)
    prefix_width = max(10, min(prefix_width, line.width // 2))

    prefix = mean_stroke_width(line.crop((0, 0, prefix_width, line.height)), threshold, ink_is_dark)
    remainder = mean_stroke_width(
        line.crop((prefix_width, 0, line.width, line.height)), threshold, ink_is_dark
    )
    if not prefix or not remainder:
        return None
    return prefix / remainder


def _sides(ocr: OcrResult, image: Image.Image, detected: dict[str, str | None]) -> dict[str, str]:
    """Which panel of the container each field appeared on.

    A single panel puts everything on the front, which is the common case and
    the right answer: 27 CFR 5.63 asks whether three fields share one field of
    vision, and on a one-panel photograph they do.
    """
    two_panels = image.width / max(image.height, 1) >= PANEL_ASPECT_RATIO
    sides: dict[str, str] = {}
    for field, value in detected.items():
        if not value:
            # Not on the label at all. That is the field's own verdict to
            # report; the field-of-vision check must not report it a second
            # time as "we could not tell where it is".
            sides[field] = ABSENT
            continue
        block = find_block(ocr, value)
        if block is None:
            continue
        if not two_panels:
            sides[field] = "front"
            continue
        centre = block.box.x + block.box.width / 2
        sides[field] = "front" if centre < image.width / 2 else "back"
    return sides


def find_block(ocr: OcrResult, value: str) -> TextBlock | None:
    """The OCR block a detected value came from, or None.

    Matching is on collapsed, case-folded text: the extraction step returns what
    the label says, and OCR block boundaries do not always agree with it.
    """
    needle = " ".join(value.split()).casefold()
    if not needle:
        return None
    candidates = [b for b in ocr.blocks if needle in " ".join(b.text.split()).casefold()]
    if candidates:
        return min(candidates, key=lambda b: len(b.text))

    # A long value wrapped across several lines — the government warning always
    # is. Merge the blocks it spans so the evidence crop shows the whole
    # statement rather than its first line.
    spanning = [
        b
        for b in ocr.blocks
        if len(b.text.strip()) > 3 and " ".join(b.text.split()).casefold() in needle
    ]
    if len(spanning) > 1 and _reconstructs(spanning, needle):
        return _merge(spanning)

    # Otherwise fall back to the block sharing the most words.
    words = set(needle.split())
    scored = [
        (len(words & set(" ".join(b.text.split()).casefold().split())), b) for b in ocr.blocks
    ]
    best_score, best = max(scored, key=lambda pair: pair[0], default=(0, None))
    return best if best_score >= max(1, len(words) // 2) else None


def _reconstructs(blocks: list[TextBlock], needle: str) -> bool:
    """True when these blocks, read in order, actually make up the value.

    Without this a short word that also appears elsewhere on the label — the
    state in an address matching the state in a class designation — dragged an
    unrelated block into the merge, and the evidence crop showed a third of the
    label instead of one line.
    """
    ordered = sorted(blocks, key=lambda b: (b.box.y, b.box.x))
    return " ".join(" ".join(b.text.split()) for b in ordered).casefold() == needle


def _merge(blocks: list[TextBlock]) -> TextBlock:
    """One block covering all of them, in reading order."""
    ordered = sorted(blocks, key=lambda b: (b.box.y, b.box.x))
    left = min(b.box.x for b in ordered)
    top = min(b.box.y for b in ordered)
    right = max(b.box.right for b in ordered)
    bottom = max(b.box.bottom for b in ordered)
    confidences = [b.confidence for b in ordered if b.confidence is not None]
    return TextBlock(
        text=" ".join(b.text for b in ordered),
        box=BoundingBox(x=left, y=top, width=right - left, height=bottom - top),
        confidence=min(confidences) if confidences else None,
    )


def measure(
    image: Image.Image, ocr: OcrResult, detected: dict[str, str | None] | None = None
) -> LayoutMetrics:
    """Everything the geometric warning checks need, or None where unavailable."""
    line_heights = [estimated_line_height(b) for b in ocr.blocks if b.text.strip()]
    median_height = _median(line_heights)

    warnings = warning_blocks(ocr)
    warning_height: float | None = None
    stroke_ratio: float | None = None
    warning_contrast: float | None = None

    if warnings:
        block = warnings[0]
        warning_height = estimated_line_height(block)
        box = block.box
        region = image.crop(
            (
                max(0, box.x - 6),
                max(0, box.y - 6),
                min(image.width, box.right + 6),
                min(image.height, box.bottom + 6),
            )
        )
        warning_contrast = contrast_ratio(region)
        stroke_ratio = _prefix_stroke_ratio(image, block, warning_height)

        # Every line of the warning leaves the baseline, not only the line
        # carrying the prefix. A shrunken warning wraps onto more lines, so
        # counting the continuations as body text dragged the median down — and
        # made the check weaker exactly as the violation got worse.
        statement = {id(block) for block in _warning_statement_blocks(ocr)}
        others = [
            estimated_line_height(b)
            for b in ocr.blocks
            if b.text.strip() and id(b) not in statement
        ]
        median_height = _median(others) or median_height

    return LayoutMetrics(
        warning_text_height=warning_height,
        median_text_height=median_height,
        warning_prefix_stroke_ratio=stroke_ratio,
        warning_contrast_ratio=warning_contrast,
        field_sides=_sides(ocr, image, detected or {}),
    )


def crop_box(image: Image.Image, box: BoundingBox, padding: int = 12) -> Image.Image | None:
    """A padded crop, clamped to the image, or None if the box falls outside it.

    OCR coordinates and the decoded frame can disagree — an orientation tag, or
    a provider returning boxes for the pre-rotation image. An inverted rectangle
    raised ValueError from inside PIL and reached the client as a bare 500.
    """
    left = max(0, min(image.width, box.x - padding))
    top = max(0, min(image.height, box.y - padding))
    right = max(0, min(image.width, box.right + padding))
    bottom = max(0, min(image.height, box.bottom + padding))
    if right - left < 2 or bottom - top < 2:
        return None
    return image.crop((left, top, right, bottom))
