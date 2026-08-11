"""Focus and exposure are different faults and must not be confused.

An agent told "too blurry" re-shoots for focus. If the real problem was the
light, they will produce another rejected photo and conclude the tool is
broken — which is precisely Dave Morrison's objection. FR-15 and
.claude/rules/error-handling.md 2 require the cause be named correctly, not
merely named.
"""

from __future__ import annotations

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from app.errors import UnreadableImageError
from app.pipeline.quality import assess, require_readable

WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)


def sharp_label() -> Image.Image:
    """A crisp, well-exposed label. Every other case here degrades this one.

    Laid out like a real one — stock-coloured rather than paper-white, with the
    warning block at the foot. A large blank white area low on the label reads
    to the glare check as a blown-out reflection, which is correct behaviour
    and the wrong thing for this fixture to be exercising.
    """
    image = Image.new("RGB", (1000, 1400), "#efece4")
    draw = ImageDraw.Draw(image)
    draw.text((80, 150), "OLD TOM DISTILLERY", fill="black")
    draw.text((80, 260), "Kentucky Straight Bourbon Whiskey", fill="black")
    draw.text((80, 340), "45% Alc./Vol. (90 Proof)", fill="black")
    draw.text((80, 420), "750 mL", fill="black")
    draw.text((80, 500), "Bottled by Old Tom Distillery, Bardstown, Kentucky", fill="black")
    # Small text carries most of the high-frequency signal and is the first
    # thing a blurred photo loses. Ten lines at the foot puts this fixture's
    # sharpness near that of a rendered corpus label, so the thresholds it
    # exercises are the ones real labels hit.
    for index in range(10):
        draw.text((80, 1120 + index * 22), WARNING[:96], fill="black")
    return image


class TestExposureIsNotFocus:
    def test_a_sharp_label_is_readable(self) -> None:
        require_readable(sharp_label())

    @pytest.mark.parametrize("brightness", [0.42, 0.30, 0.20, 0.16, 0.14])
    def test_underexposure_alone_never_reports_blur(self, brightness: float) -> None:
        # Dimming does not move a single edge. Whatever we say about this
        # image, "out of focus" is false.
        darkened = ImageEnhance.Brightness(sharp_label()).enhance(brightness)
        try:
            require_readable(darkened)
        except UnreadableImageError as raised:
            assert raised.code != "image_too_blurry", (
                f"a sharp label dimmed to {brightness} was reported as blurry; "
                "the agent would re-shoot for focus and hit the same wall"
            )

    @pytest.mark.parametrize("brightness", [0.42, 0.30, 0.20, 0.16, 0.14])
    def test_the_focus_reading_itself_barely_moves(self, brightness: float) -> None:
        # The invariant behind the rule above. Asserting only on the error code
        # would still pass if the focus check were deleted outright.
        bright = assess(sharp_label()).focus
        dark = assess(ImageEnhance.Brightness(sharp_label()).enhance(brightness)).focus
        assert abs(dark - bright) < 1.0, (
            f"focus moved {bright:.2f} -> {dark:.2f} on a dimmed copy of the same "
            "sharp label; exposure is leaking into the focus measure again"
        )


class TestTheRealFaultsStillFire:
    def test_a_genuinely_blurred_label_is_reported_as_blurry(self) -> None:
        blurred = sharp_label().filter(ImageFilter.GaussianBlur(11))
        with pytest.raises(UnreadableImageError) as raised:
            require_readable(blurred)
        assert raised.value.code == "image_too_blurry"

    def test_a_blurred_label_stays_blurry_when_it_is_also_dim(self) -> None:
        # The normalisation must not launder a genuinely unfocused photo into
        # a readable one just because it is dark.
        ruined = ImageEnhance.Brightness(
            sharp_label().filter(ImageFilter.GaussianBlur(11))
        ).enhance(0.3)
        with pytest.raises(UnreadableImageError) as raised:
            require_readable(ruined)
        assert raised.value.code == "image_too_blurry"

    def test_a_label_lost_in_the_dark_is_reported_as_dark(self) -> None:
        pitch = ImageEnhance.Brightness(sharp_label()).enhance(0.06)
        with pytest.raises(UnreadableImageError) as raised:
            require_readable(pitch)
        assert raised.value.code == "image_too_dark"


def speckled(image: Image.Image, sigma: int = 2) -> Image.Image:
    """Zero-mean sensor grain, of the amount every phone JPEG already carries."""
    noise = Image.effect_noise(image.size, sigma).convert("RGB")
    return ImageChops.add(image, noise, scale=1, offset=-128)


class TestNoiseIsNotDetail:
    """Normalising for exposure must not let grain masquerade as sharpness.

    Scaling by the full min-to-max range does exactly that: the range collapses
    on a low-contrast frame, the gain goes up without bound, and a photograph
    blurred past reading scores as sharp. That is the same wrong-cause failure
    as the bug this module was fixed for, pointing the other way — the agent is
    told the text could not be read when the truth is the photo is out of focus.
    """

    @pytest.mark.parametrize(
        ("radius", "contrast", "label"),
        [
            (11, 1.00, "blurred, normally exposed"),
            (8, 0.35, "blurred and washed out"),
            (8, 0.20, "blurred and heavily washed out"),
        ],
    )
    def test_a_blurred_label_with_sensor_grain_is_still_blurry(
        self, radius: int, contrast: float, label: str
    ) -> None:
        ruined = speckled(
            ImageEnhance.Contrast(sharp_label().filter(ImageFilter.GaussianBlur(radius))).enhance(
                contrast
            )
        )
        with pytest.raises(UnreadableImageError) as raised:
            require_readable(ruined)
        assert raised.value.code == "image_too_blurry", f"{label} was accepted as readable"

    def test_grain_alone_does_not_make_a_sharp_label_unreadable(self) -> None:
        require_readable(speckled(sharp_label()))


def on_white_stock(warning_present: bool) -> Image.Image:
    """A label printed on pure white, with or without its warning.

    Carries dense body copy in its upper half so that removing the warning
    leaves the image sharp — otherwise the focus gate fires first and the case
    under test never runs.
    """
    image = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(image)
    draw.text((80, 120), "OLD TOM DISTILLERY", fill="black")
    draw.text((80, 200), "Kentucky Straight Bourbon Whiskey", fill="black")
    draw.text((80, 260), "45% Alc./Vol. (90 Proof)", fill="black")
    draw.text((80, 320), "750 mL", fill="black")
    for index in range(18):
        draw.text((80, 380 + index * 22), WARNING[:96], fill="black")
    draw.text((80, 800), "Bottled by Old Tom Distillery, Bardstown, Kentucky", fill="black")
    if warning_present:
        for index in range(10):
            draw.text((80, 1120 + index * 22), WARNING[:96], fill="black")
    return image


class TestBlankPaperIsNotAReflection:
    """A missing warning must reach the rule engine as a violation.

    The glare threshold was clamped to 255 so the check would not be dead code
    on white stock. That made it worse than dead: a blank bottom margin has
    mean 255 and no variation, which satisfies both washed-strip conditions —
    so a label that simply omits its government warning was reported as an
    image problem and never checked at all. The 16.21 violation disappeared
    behind a complaint about the photograph.

    Glare is light *brighter than the label's own background*. On pure white
    there is no headroom above the background, so it cannot be detected, and
    the README says so. Not detecting it is the honest outcome; inventing it is
    not.
    """

    def test_a_white_label_missing_its_warning_is_not_called_glare(self) -> None:
        require_readable(on_white_stock(warning_present=False))

    def test_a_white_label_with_its_warning_is_readable_too(self) -> None:
        require_readable(on_white_stock(warning_present=True))

    def test_glare_is_still_caught_where_there_is_headroom_to_see_it(self) -> None:
        # Cream stock, so a blown-out white band is genuinely brighter than the
        # label around it and the check has something to measure. Built on the
        # sharp label so focus is not what fails first.
        image = on_white_stock(warning_present=True)
        # Tint the stock so a blown-out band is genuinely brighter than it.
        image = Image.blend(image, Image.new("RGB", image.size, "#e8e4d8"), 0.35)
        ImageDraw.Draw(image).rectangle((0, 980, 1000, 1400), fill="white")
        with pytest.raises(UnreadableImageError) as raised:
            require_readable(image)
        assert raised.value.code == "glare_obscures_text"
