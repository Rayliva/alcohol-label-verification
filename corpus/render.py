"""Render synthetic label images with known ground truth.

Rendering (rather than image generation) is used where the corpus needs
surgical control or volume — see docs/PRD.md → Test corpus. The generator knows
exactly what it drew, so expected verdicts are derived rather than hand-labeled.

The statutory warning is imported from the rule engine, not copied. Two copies
of fifty words of statute are one edit away from a corpus that asserts the
opposite of what it claims.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.rules.warning import STATUTORY_WARNING, WARNING_PREFIX  # noqa: E402

# One source for the statutory text: app/rules/warning.py, verified against
# Cornell LII on 2026-08-09. See .claude/rules/verify-regulations.md
GOVERNMENT_WARNING = STATUTORY_WARNING

_FONT_CANDIDATES: list[tuple[str, str]] = [
    # (regular, bold)
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ),
]

# Serif alternates, so the corpus is not four colourways of one typeface.
_SERIF_CANDIDATES: list[tuple[str, str]] = [
    ("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesbd.ttf"),
    ("C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/georgiab.ttf"),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    ),
]


def _resolve_fonts(serif: bool = False) -> tuple[str, str]:
    """Locate a regular/bold TTF pair.

    TODO: vendor DejaVu into corpus/fonts/ so Docker and CI do not depend on
    system fonts. Tracked for Phase 1.
    """
    candidates = (_SERIF_CANDIDATES + _FONT_CANDIDATES) if serif else _FONT_CANDIDATES
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            return regular, bold
    raise RuntimeError(
        "No regular/bold TTF pair found. Install DejaVu fonts or vendor them into corpus/fonts/."
    )


@dataclass(frozen=True)
class Design:
    """How a label looks, independent of what it says.

    Four of these exist so OCR is exercised against more than one colourway of
    one typeface. Nothing here changes whether a label is compliant.
    """

    name: str
    background: str = "#faf8f2"
    text_colour: str = "black"
    serif: bool = False
    align: str = "center"
    brand_size: int = 76
    class_size: int = 38
    body_size: int = 30


CLASSIC = Design(name="classic", serif=True)
MODERN = Design(name="modern", background="#ffffff", align="left", brand_size=68)
DARK = Design(name="dark", background="#14181d", text_colour="#f2efe6", serif=True)
COMPACT = Design(
    name="compact",
    background="#eef1ec",
    brand_size=58,
    class_size=32,
    body_size=26,
)

DESIGNS = (CLASSIC, MODERN, DARK, COMPACT)


@dataclass
class LabelSpec:
    """Everything that appears on a rendered label, plus how it is drawn.

    The styling flags exist so a single field can be violated surgically —
    one violation per label (docs/PRD.md → Test corpus).
    """

    label_id: str
    brand: str | None = "OLD TOM DISTILLERY"
    class_type: str | None = "Kentucky Straight Bourbon Whiskey"
    alcohol_content: str | None = "45% Alc./Vol. (90 Proof)"
    net_contents: str | None = "750 mL"
    bottler: str | None = "Bottled by Old Tom Distillery, Bardstown, Kentucky"
    warning: str | None = GOVERNMENT_WARNING

    # Styling / violation controls
    warning_bold_prefix: bool = True
    warning_scale: float = 1.0  # relative to body text; <1.0 shrinks it
    warning_bg: str | None = None  # set close to the text colour to kill contrast
    warning_colour: str | None = None
    design: Design = CLASSIC
    # Fields moved to a second panel, for the 27 CFR 5.63 field-of-vision check.
    back_fields: tuple[str, ...] = ()
    width: int = 1000
    height: int = 1400

    notes: str = ""
    expected: dict[str, str] = field(default_factory=dict)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if font.getlength(trial) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_panel(
    draw: ImageDraw.ImageDraw,
    spec: LabelSpec,
    origin_x: int,
    panel_width: int,
    entries: list[tuple[str, ImageFont.FreeTypeFont, int]],
) -> None:
    margin = 70
    inner = panel_width - 2 * margin
    y = 150
    for text, font, gap in entries:
        for line in _wrap(text, font, inner):
            width = font.getlength(line)
            x = origin_x + ((panel_width - width) / 2 if spec.design.align == "center" else margin)
            draw.text((x, y), line, font=font, fill=spec.design.text_colour)
            y += font.size + 8
        y += gap


def _draw_warning(
    draw: ImageDraw.ImageDraw, spec: LabelSpec, origin_x: int, panel_width: int
) -> None:
    if not spec.warning:
        return
    regular_path, bold_path = _resolve_fonts(spec.design.serif)
    margin = 70
    inner = panel_width - 2 * margin
    size = max(7, int(spec.design.body_size * 0.62 * spec.warning_scale))
    regular = ImageFont.truetype(regular_path, size)
    bold = ImageFont.truetype(bold_path, size)
    colour = spec.warning_colour or spec.design.text_colour

    lines = _wrap(spec.warning, regular, inner)
    block_height = len(lines) * (size + 5)
    y = spec.height - margin - block_height

    if spec.warning_bg and spec.warning_bg != spec.design.background:
        draw.rectangle(
            [
                origin_x + margin - 14,
                y - 14,
                origin_x + panel_width - margin + 14,
                y + block_height + 14,
            ],
            fill=spec.warning_bg,
        )

    prefix = WARNING_PREFIX if spec.warning.upper().startswith(WARNING_PREFIX) else None
    for line in lines:
        x = float(origin_x + margin)
        # Bold only the statutory prefix, and only on the line carrying it.
        if prefix and spec.warning_bold_prefix and line.upper().startswith(prefix):
            as_printed = line[: len(prefix)]
            draw.text((x, y), as_printed, font=bold, fill=colour)
            x += bold.getlength(as_printed)
            draw.text((x, y), line[len(prefix) :], font=regular, fill=colour)
        else:
            draw.text((x, y), line, font=regular, fill=colour)
        y += size + 5


def render(spec: LabelSpec, out_dir: Path) -> Path:
    """Render `spec` to a PNG and return its path."""
    regular_path, bold_path = _resolve_fonts(spec.design.serif)
    panels = 2 if spec.back_fields else 1
    image = Image.new("RGB", (spec.width * panels, spec.height), spec.design.background)
    draw = ImageDraw.Draw(image)

    brand_font = ImageFont.truetype(bold_path, spec.design.brand_size)
    class_font = ImageFont.truetype(regular_path, spec.design.class_size)
    body_font = ImageFont.truetype(regular_path, spec.design.body_size)

    available: list[tuple[str, str, ImageFont.FreeTypeFont, int]] = [
        ("brand", spec.brand or "", brand_font, 40),
        ("class_type", spec.class_type or "", class_font, 70),
        ("alcohol_content", spec.alcohol_content or "", body_font, 16),
        ("net_contents", spec.net_contents or "", body_font, 60),
        ("bottler", spec.bottler or "", body_font, 40),
    ]

    front = [
        (text, font, gap)
        for name, text, font, gap in available
        if text and name not in spec.back_fields
    ]
    back = [
        (text, font, gap)
        for name, text, font, gap in available
        if text and name in spec.back_fields
    ]

    _draw_panel(draw, spec, 0, spec.width, front)
    if panels == 2:
        # A visible seam, so the two sides read as two sides of a container.
        draw.line([(spec.width, 0), (spec.width, spec.height)], fill="#999999", width=4)
        _draw_panel(draw, spec, spec.width, spec.width, back)

    # The warning goes on the panel carrying the back-label content, which is
    # where a real label puts it.
    _draw_warning(draw, spec, spec.width * (panels - 1), spec.width)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{spec.label_id}.png"
    image.save(path)
    return path


if __name__ == "__main__":
    out = REPO_ROOT / "corpus" / "out"
    samples = [
        LabelSpec(label_id="spike-clean", notes="fully compliant baseline"),
        LabelSpec(
            label_id="spike-warning-title-case",
            warning=GOVERNMENT_WARNING.replace(WARNING_PREFIX, "Government Warning"),
            notes="warning prefix in title case — must FAIL",
        ),
        LabelSpec(
            label_id="spike-warning-tiny",
            warning_scale=0.4,
            notes="warning at 40% size — must FAIL on proportion",
        ),
    ]
    for sample in samples:
        print(render(sample, out))
