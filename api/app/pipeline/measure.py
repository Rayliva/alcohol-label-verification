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
from app.pipeline.quality import assess
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


def _label_white_point(image: Image.Image) -> float:
    """What white reads as on this photograph, ignoring the brightest 1%."""
    return max(_percentile(image.convert("L").histogram(), 0.99), 1.0)


def contrast_ratio(region: Image.Image, white_point: float | None = None) -> float | None:
    """WCAG contrast between the darkest and lightest tones present.

    27 CFR 16.22 asks whether the warning separates from its background *on the
    label*. What we have is a photograph, and WCAG's (L1+0.05)/(L2+0.05) is not
    scale-invariant: dim the same label and both luminances fall toward zero
    while the constant stays put, so the ratio collapses toward 1. Measured on
    one compliant label, exposure alone moved it 4.18 -> 1.48 and turned a
    correct PASS into a government-warning FAIL — a violation that does not
    exist, invented by the lighting.

    `white_point` rescales the region as though the label had been exposed
    properly. It must come from the **whole label**, never from this region:
    normalising a region against its own range would stretch a genuinely faint
    warning into a crisp one and delete the very defect this check exists to
    find.
    """
    grey = region.convert("L")
    if grey.width < 4 or grey.height < 4:
        return None
    if white_point and white_point > 0:
        gain = 255.0 / white_point
        grey = grey.point(lambda value: min(255, int(value * gain)))
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
        # Wide enough to be two panels. This is a heuristic and it is known to
        # be imperfect: a single-panel landscape export at 1.75 is treated the
        # same as the genuinely two-panel artwork the corpus renders at 1.43,
        # so the same blocks can pass at 1000x1400 and fail at 1400x800.
        #
        # Kept, because the alternative costs more than it saves. Declining to
        # judge whenever the frame is wide would drop a real check on every
        # genuine two-panel label; an uncalibrated photograph carries no better
        # signal than this one. Recorded in docs/audit-findings.md as B3.
        centre = block.box.x + block.box.width / 2
        sides[field] = "front" if centre < image.width / 2 else "back"
    return sides


def _squash(text: str) -> str:
    """Case-folded with ALL whitespace removed, not just collapsed.

    Cloud Vision joins wrapped lines without a space: the 006 sample's
    two-line title comes back as one block reading "OLD TOMDISTILLERY", and
    the government warning as "womenshould not ... risk ofbirth defects".
    Extraction restores the spaces, so any comparison that keeps them can
    never match a block whose line break was swallowed — the brand's evidence
    crop fell through to the bottler line, which merely mentions the name.
    """
    return "".join(text.split()).casefold()


def find_block(ocr: OcrResult, value: str) -> TextBlock | None:
    """The OCR block a detected value came from, or None.

    Matching is on squashed, case-folded text: the extraction step returns
    what the label says, and OCR block boundaries — including where the line
    breaks were — do not always agree with it.
    """
    needle = _squash(value)
    if not needle:
        return None
    candidates = [b for b in ocr.blocks if needle in _squash(b.text)]
    # A block that IS the value settles it — checked across every candidate,
    # not only the shortest, because raw length counts whitespace and a glued
    # containing block can be "shorter" than the exact one. A block that merely
    # contains the value does not settle it: the spanning reconstruction below
    # still gets a chance to find the blocks that together are exactly the
    # value — a two-line title split into two OCR blocks must beat a bottler
    # line that mentions the brand.
    exact = [b for b in candidates if _squash(b.text) == needle]
    if exact:
        return min(exact, key=lambda b: len(b.text))
    best = min(candidates, key=lambda b: len(b.text)) if candidates else None

    # A value wrapped across several lines — the government warning always is,
    # and so is a two-line brand title. Merge the blocks it spans so the
    # evidence crop shows the whole statement rather than its first line.
    spanning = [b for b in ocr.blocks if len(b.text.strip()) > 3 and _squash(b.text) in needle]
    reconstructed = _reconstruct(spanning, needle)
    if reconstructed is not None:
        return _merge(reconstructed)
    if best is not None:
        return best

    # Otherwise fall back to the block sharing the most words. Half of them
    # was too loose a bar for a claim about evidence: a two-word value matched
    # any block sharing one word, and the crop could be an unrelated line
    # presented as the place the value came from (audit C3). Two thirds keeps
    # the crop when OCR mangles one word among several and refuses it when
    # most of the value is simply not there.
    words = set(value.casefold().split())
    scored = [
        (len(words & set(" ".join(b.text.split()).casefold().split())), b) for b in ocr.blocks
    ]
    best_score, fallback = max(scored, key=lambda pair: pair[0], default=(0, None))
    return fallback if best_score >= max(1, -(-2 * len(words) // 3)) else None


def _reconstruct(blocks: list[TextBlock], needle: str) -> list[TextBlock] | None:
    """The subset of blocks that, read in order, make up the value — or None.

    Greedy: walk the candidates in reading order and keep each one that
    continues the needle from where the last kept block left off. A stray
    fragment whose text happens to sit somewhere inside the needle is skipped
    rather than allowed to veto the merge — demanding that every candidate
    participate let one junk OCR fragment cost the crop its region.

    The exact-continuation requirement is also what keeps unrelated blocks
    out: a short word that appears elsewhere on the label — the state in an
    address matching the state in a class designation — does not continue the
    needle at the current position, so it never drags the merge across a third
    of the label. The needle arrives already squashed.
    """
    ordered = sorted(blocks, key=lambda b: (b.box.y, b.box.x))
    used: list[TextBlock] = []
    position = 0
    for candidate in ordered:
        squashed = _squash(candidate.text)
        if needle.startswith(squashed, position):
            used.append(candidate)
            position += len(squashed)
    return used if position == len(needle) and len(used) > 1 else None


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


# Readable and measurable are different bars. Stroke weight is the most
# fragile thing here: blur smears the bold heading and the body text toward the
# same apparent thickness, so the ratio collapses and, past a point, inverts. On
# the corpus a compliant label reads 1.35, a genuinely un-bold one 1.06, and a
# compliant one photographed slightly soft 0.90 — below the real defect.
#
# Measured focus (app/pipeline/quality.py) separates them cleanly: the soft
# label reads 5.19 while every other compliant label sits at 12.11-15.62 and all
# three genuine warning defects at 13.51-15.43. 8.0 is the geometric midpoint of
# 5.19 and 12.11, ~1.5x either side, and well clear of every real defect.
MIN_FOCUS_FOR_GEOMETRY = 8.0


def measure(
    image: Image.Image, ocr: OcrResult, detected: dict[str, str | None] | None = None
) -> LayoutMetrics:
    """Everything the geometric warning checks need, or None where unavailable.

    Fine measurements are withheld from an image too soft to support them. The
    checks then take the no-measurement path and ask a person to look, which is
    the honest answer — and cannot become a PASS, so nothing is hidden.
    """
    line_heights = [estimated_line_height(b) for b in ocr.blocks if b.text.strip()]
    median_height = _median(line_heights)

    # Text height survives softness; stroke weight and contrast do not.
    fine_detail_is_trustworthy = assess(image).focus >= MIN_FOCUS_FOR_GEOMETRY

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
        if fine_detail_is_trustworthy:
            warning_contrast = contrast_ratio(region, white_point=_label_white_point(image))
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
