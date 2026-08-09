"""Render synthetic label images with known ground truth.

Rendering (rather than image generation) is used where the corpus needs
surgical control or volume — see docs/PRD.md → Test corpus. The generator
knows exactly what it drew, so expected verdicts are derived rather than
hand-labeled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 27 CFR 16.21, verbatim. One continuous statement; (1) and (2) are inline.
# Verified against Cornell LII 2026-08-09. Do not edit without re-verifying.
# See .claude/rules/verify-regulations.md
GOVERNMENT_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

WARNING_PREFIX = "GOVERNMENT WARNING:"

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


def _resolve_fonts() -> tuple[str, str]:
    """Locate a regular/bold TTF pair.

    TODO: vendor DejaVu into corpus/fonts/ so Docker and CI do not depend on
    system fonts. Tracked for Phase 1.
    """
    for regular, bold in _FONT_CANDIDATES:
        if Path(regular).exists() and Path(bold).exists():
            return regular, bold
    raise RuntimeError(
        "No regular/bold TTF pair found. Install DejaVu fonts or vendor them "
        "into corpus/fonts/."
    )


@dataclass
class LabelSpec:
    """Everything that appears on a rendered label, plus how it is drawn.

    The styling flags exist so a single field can be violated surgically —
    one violation per label (docs/PRD.md → Test corpus).
    """

    label_id: str
    brand: str = "OLD TOM DISTILLERY"
    class_type: str = "Kentucky Straight Bourbon Whiskey"
    alcohol_content: str = "45% Alc./Vol. (90 Proof)"
    net_contents: str = "750 mL"
    bottler: str = "Bottled by Old Tom Distillery, Bardstown, Kentucky"
    warning: str = GOVERNMENT_WARNING

    # Styling / violation controls
    warning_bold_prefix: bool = True
    warning_scale: float = 1.0  # relative to body text; <1.0 shrinks it
    warning_bg: str = "white"  # set equal to text colour to kill contrast
    text_colour: str = "black"
    background: str = "#faf8f2"
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


def render(spec: LabelSpec, out_dir: Path) -> Path:
    """Render `spec` to a PNG and return its path."""
    regular_path, bold_path = _resolve_fonts()
    img = Image.new("RGB", (spec.width, spec.height), spec.background)
    draw = ImageDraw.Draw(img)

    margin = 70
    inner = spec.width - 2 * margin
    body_size = 30
    y = 150

    def centred(text: str, font: ImageFont.FreeTypeFont, y_pos: int, gap: int) -> int:
        for line in _wrap(text, font, inner):
            w = font.getlength(line)
            draw.text(((spec.width - w) / 2, y_pos), line, font=font, fill=spec.text_colour)
            y_pos += font.size + 8
        return y_pos + gap

    brand_font = ImageFont.truetype(bold_path, 76)
    class_font = ImageFont.truetype(regular_path, 38)
    body_font = ImageFont.truetype(regular_path, body_size)

    y = centred(spec.brand, brand_font, y, 40)
    y = centred(spec.class_type, class_font, y, 70)
    y = centred(spec.alcohol_content, body_font, y, 16)
    y = centred(spec.net_contents, body_font, y, 60)
    y = centred(spec.bottler, body_font, y, 40)

    # --- Government warning, bottom-anchored ---
    if spec.warning:
        w_size = max(8, int(body_size * 0.62 * spec.warning_scale))
        w_regular = ImageFont.truetype(regular_path, w_size)
        w_bold = ImageFont.truetype(bold_path, w_size)

        lines = _wrap(spec.warning, w_regular, inner)
        block_h = len(lines) * (w_size + 5)
        wy = spec.height - margin - block_h

        if spec.warning_bg != spec.background:
            draw.rectangle(
                [margin - 14, wy - 14, spec.width - margin + 14, wy + block_h + 14],
                fill=spec.warning_bg,
            )

        prefix = WARNING_PREFIX if spec.warning.startswith(WARNING_PREFIX) else None
        for line in lines:
            x = float(margin)
            # Bold only the statutory prefix, and only on the line carrying it.
            if prefix and spec.warning_bold_prefix and line.startswith(prefix):
                draw.text((x, wy), prefix, font=w_bold, fill=spec.text_colour)
                x += w_bold.getlength(prefix)
                rest = line[len(prefix) :]
                draw.text((x, wy), rest, font=w_regular, fill=spec.text_colour)
            else:
                draw.text((x, wy), line, font=w_regular, fill=spec.text_colour)
            wy += w_size + 5

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{spec.label_id}.png"
    img.save(path)
    return path


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "out"
    samples = [
        LabelSpec(label_id="spike-clean", notes="fully compliant baseline"),
        LabelSpec(
            label_id="spike-warning-title-case",
            warning=GOVERNMENT_WARNING.replace(WARNING_PREFIX, "Government Warning:"),
            notes="warning prefix in title case — must FAIL",
        ),
        LabelSpec(
            label_id="spike-warning-tiny",
            warning_scale=0.4,
            notes="warning at 40% size — must NEEDS_REVIEW on proportion",
        ),
    ]
    for s in samples:
        print(render(s, out))
