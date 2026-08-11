"""Readable is not the same as measurable.

A lightly blurred label can be read perfectly well and still be the wrong thing
to measure stroke weight on. Blur smears the bold heading and the body text
toward the same apparent thickness, so the ratio collapses — measured on the
corpus, a compliant label reads 1.35, a genuinely un-bold one reads 1.06, and a
compliant one photographed slightly soft reads 0.90. The measurement does not
merely degrade, it inverts and lands below the real defect.

So a verdict drawn from it is a statement about the photograph, not the label.
Where the image is too soft to measure, the fine geometric measurements are not
reported at all, and the existing path takes over: a check with no measurement
returns NEEDS_REVIEW and asks a person to look. It can never become a PASS, so
this cannot hide a violation — only stop inventing one.
"""

from __future__ import annotations

from PIL import Image

from app.ocr.base import BoundingBox, OcrResult, TextBlock
from app.pipeline.measure import measure
from app.pipeline.quality import assess

WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects."
)


def ocr_over(image: Image.Image) -> OcrResult:
    width, height = image.size
    blocks = (
        TextBlock(
            text="OLD TOM DISTILLERY",
            box=BoundingBox(x=70, y=150, width=width - 140, height=76),
            confidence=0.98,
        ),
        TextBlock(
            text=WARNING,
            box=BoundingBox(x=70, y=int(height * 0.78), width=width - 140, height=90),
            confidence=0.97,
        ),
    )
    return OcrResult(
        full_text="\n".join(b.text for b in blocks),
        blocks=blocks,
        image_width=width,
        image_height=height,
        engine="test",
        latency_ms=0.0,
    )


def corpus(name: str) -> Image.Image:
    return Image.open(f"../corpus/out/{name}.png").convert("RGB")


class TestASoftImageIsNotMeasured:
    def test_stroke_weight_is_not_reported_from_a_soft_photograph(self) -> None:
        image = corpus("t4-blur-light")
        assert assess(image).focus < 8.0, "fixture is no longer the soft case"
        metrics = measure(image, ocr_over(image))
        assert metrics.warning_prefix_stroke_ratio is None

    def test_contrast_is_not_reported_from_a_soft_photograph(self) -> None:
        image = corpus("t4-blur-light")
        assert measure(image, ocr_over(image)).warning_contrast_ratio is None


class TestASharpImageIsStillMeasured:
    def test_a_clean_label_still_reports_both(self) -> None:
        image = corpus("t1-clean-classic-1")
        metrics = measure(image, ocr_over(image))
        assert metrics.warning_prefix_stroke_ratio is not None
        assert metrics.warning_contrast_ratio is not None

    def test_a_genuinely_unbold_label_is_still_measured(self) -> None:
        # The defect must survive. Suppressing measurement on a sharp image
        # would turn every real violation into a shrug.
        image = corpus("t2-warning-not-bold")
        assert assess(image).focus >= 8.0
        assert measure(image, ocr_over(image)).warning_prefix_stroke_ratio is not None

    def test_a_genuinely_faint_warning_is_still_measured(self) -> None:
        image = corpus("t2-warning-low-contrast")
        assert measure(image, ocr_over(image)).warning_contrast_ratio is not None

    def test_an_underexposed_but_sharp_label_is_still_measured(self) -> None:
        # Exposure was already made not to matter; this guards that it stays so.
        image = corpus("t4-low-light")
        assert measure(image, ocr_over(image)).warning_contrast_ratio is not None
