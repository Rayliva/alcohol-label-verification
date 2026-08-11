"""How a label was lit is not whether its warning is legible.

27 CFR 16.22 asks whether the warning separates from its background on the
label. WCAG's (L1+0.05)/(L2+0.05) is not scale-invariant — dim the photograph
and both luminances fall toward zero while the constant does not, so the ratio
collapses toward 1. Left uncorrected that turns a correctly-lit compliant
label into a government-warning FAIL as soon as someone photographs it in a
dim room: a violation invented by the lighting.

The correction must not go too far. Normalising a warning region against its
own range would stretch a genuinely faint warning into a crisp one and delete
the defect this check exists to find, so the scale comes from the whole label.
"""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw, ImageEnhance

from app.pipeline.measure import _label_white_point, contrast_ratio


def warning_region(ink: str, background: str = "white") -> Image.Image:
    region = Image.new("RGB", (600, 120), background)
    draw = ImageDraw.Draw(region)
    for line in range(4):
        draw.text((10, 8 + line * 26), "GOVERNMENT WARNING: " * 3, fill=ink)
    return region


def on_a_label(region: Image.Image, brightness: float) -> tuple[Image.Image, float]:
    """The region as it appears on a photograph of the whole label."""
    label = Image.new("RGB", (900, 1300), "white")
    label.paste(region, (100, 1000))
    dimmed = ImageEnhance.Brightness(label).enhance(brightness)
    return dimmed.crop((100, 1000, 700, 1120)), _label_white_point(dimmed)


class TestExposureDoesNotChangeTheVerdict:
    @pytest.mark.parametrize("brightness", [1.0, 0.7, 0.5, 0.35, 0.25])
    def test_a_crisp_warning_reads_the_same_however_it_was_lit(self, brightness: float) -> None:
        reference, reference_white = on_a_label(warning_region("black"), 1.0)
        dimmed, white = on_a_label(warning_region("black"), brightness)
        expected = contrast_ratio(reference, white_point=reference_white)
        actual = contrast_ratio(dimmed, white_point=white)
        assert expected is not None and actual is not None
        # Within a fifth of the reading: JPEG-free synthetic input, so any
        # larger drift means exposure is still leaking into the measurement.
        assert abs(actual - expected) / expected < 0.2, (
            f"contrast read {expected:.2f} at full exposure and {actual:.2f} at "
            f"{brightness}; the printed label never changed"
        )

    def test_uncorrected_measurement_really_does_collapse(self) -> None:
        # The bug, pinned. Without the white point the same label loses
        # contrast purely by being photographed in less light.
        bright, _ = on_a_label(warning_region("black"), 1.0)
        dim, _ = on_a_label(warning_region("black"), 0.25)
        assert contrast_ratio(dim) < contrast_ratio(bright) / 2


class TestTheRealDefectSurvives:
    def test_a_faint_warning_still_reads_faint(self) -> None:
        faint, white = on_a_label(warning_region("#b9b9b9"), 1.0)
        ratio = contrast_ratio(faint, white_point=white)
        assert ratio is not None and ratio < 4.5

    def test_and_still_reads_faint_when_the_photo_is_dim(self) -> None:
        # The correction must not launder a genuine defect into a pass.
        faint, white = on_a_label(warning_region("#b9b9b9"), 0.35)
        ratio = contrast_ratio(faint, white_point=white)
        assert ratio is not None and ratio < 4.5

    def test_a_crisp_warning_clears_the_bar(self) -> None:
        crisp, white = on_a_label(warning_region("black"), 1.0)
        ratio = contrast_ratio(crisp, white_point=white)
        assert ratio is not None and ratio >= 4.5
