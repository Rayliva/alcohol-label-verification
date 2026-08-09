"""The labeled test corpus.

Renders every label the accuracy suite scores against, and writes the ground
truth beside it in `corpus/fixtures/expected.json`.

**Ground truth is declared here by hand, from the regulation.** It is never
computed by the rule engine — deriving the expectation from the code under test
would assert only that the code agrees with itself. Each variant states the one
thing it violates and what verdict that should produce; every other field is
expected to PASS, which is how false positives get caught.

Design principle, from docs/PRD.md → Test corpus: **one violation per label.**
If a label breaks three rules and the tool misses one, you cannot tell which
check failed.

Usage:

    python corpus/generate.py --all
    python corpus/generate.py --tier 2
    python corpus/generate.py --id t2-warning-title-case
    python corpus/generate.py --batch 200
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))
sys.path.insert(0, str(REPO_ROOT))

from corpus.render import (  # noqa: E402
    COMPACT,
    DESIGNS,
    GOVERNMENT_WARNING,
    MODERN,
    LabelSpec,
    render,
)

from app.rules.beverage_types import rules_for  # noqa: E402
from app.rules.warning import WARNING_PREFIX  # noqa: E402

OUT_DIR = REPO_ROOT / "corpus" / "out"
FIXTURES = REPO_ROOT / "corpus" / "fixtures"

_SEVERITY = {"pass": 0, "needs_review": 1, "fail": 2}

# Conditional on imports; absent from every domestic label here, so the engine
# skips it and the corpus does not declare an expectation for it.
_CONDITIONAL_FIELDS = {"country_of_origin"}


@dataclass(frozen=True)
class Variant:
    """One label, what the application says about it, and what should happen."""

    label_id: str
    tier: int
    beverage_type: str
    spec: LabelSpec
    application: dict[str, str | None]
    expected_fields: dict[str, str]
    expected_overall: str
    notes: str
    scored: bool = True
    excluded_reason: str = ""
    # True when the verdict depends on a measurement taken from the image —
    # stroke weight, text height, contrast, which side a field sits on. The
    # accuracy suite reports these separately rather than counting a missing
    # measurement as a wrong answer.
    requires_layout: bool = False
    degradation: str | None = None

    @property
    def image_name(self) -> str:
        return f"{self.label_id}.png"


# --- Products -----------------------------------------------------------------
#
# Three real-looking spirits, so the corpus is not one label repeated. Each is
# internally consistent: proof is twice the percentage, and the application
# declares exactly what the artwork prints.

OLD_TOM = {
    "brand_name": "OLD TOM DISTILLERY",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45% Alc./Vol. (90 Proof)",
    "net_contents": "750 mL",
    "bottler_address": "Bottled by Old Tom Distillery, Bardstown, Kentucky",
}

STONES_THROW = {
    "brand_name": "STONE'S THROW",
    "class_type": "Straight Rye Whiskey",
    "alcohol_content": "50% Alc./Vol. (100 Proof)",
    "net_contents": "750 mL",
    "bottler_address": "Distilled and bottled by Stone's Throw Spirits, Louisville, Kentucky",
}

HARBOR_LIGHT = {
    "brand_name": "HARBOR LIGHT",
    "class_type": "London Dry Gin",
    "alcohol_content": "47% Alc./Vol. (94 Proof)",
    "net_contents": "700 mL",
    "bottler_address": "Bottled by Harbor Light Distilling Co., Portland, Maine",
}

PRODUCTS = (OLD_TOM, STONES_THROW, HARBOR_LIGHT)


def _spec_from(product: dict[str, str | None], label_id: str, **overrides: object) -> LabelSpec:
    """A label that prints exactly what the application declares."""
    fields: dict[str, object] = {
        "label_id": label_id,
        "brand": product["brand_name"],
        "class_type": product["class_type"],
        "alcohol_content": product["alcohol_content"],
        "net_contents": product["net_contents"],
        "bottler": product["bottler_address"],
    }
    fields.update(overrides)
    return LabelSpec(**fields)  # type: ignore[arg-type]


def _expectations(beverage_type: str, deviations: dict[str, str]) -> dict[str, str]:
    """PASS on everything the rule set checks, except what this label breaks."""
    fields = {
        rule.field: "pass"
        for rule in rules_for(beverage_type).fields
        if rule.field not in _CONDITIONAL_FIELDS
    }
    unknown = set(deviations) - set(fields)
    if unknown:
        raise ValueError(f"{beverage_type} has no field(s) {unknown}")
    return {**fields, **deviations}


def variant(
    label_id: str,
    tier: int,
    notes: str,
    *,
    spec: LabelSpec,
    application: dict[str, str | None],
    deviations: dict[str, str] | None = None,
    beverage_type: str = "spirits",
    unreadable: bool = False,
    **kwargs: object,
) -> Variant:
    if unreadable:
        expected_fields: dict[str, str] = {}
        overall = "unreadable"
    else:
        expected_fields = _expectations(beverage_type, deviations or {})
        overall = max(expected_fields.values(), key=lambda v: _SEVERITY[v])
    return Variant(
        label_id=label_id,
        tier=tier,
        beverage_type=beverage_type,
        spec=spec,
        application=application,
        expected_fields=expected_fields,
        expected_overall=overall,
        notes=notes,
        **kwargs,  # type: ignore[arg-type]
    )


# --- Tier 1 — clean baseline ---------------------------------------------------
#
# The PRD calls for 4 designs across 3 beverage types. Wine and malt rule sets
# are Phase 4, so Phase 1 renders 4 designs across the 3 spirits products
# instead; the wine and malt baselines arrive with their rule sets. Recorded as
# a deviation rather than absorbed silently.


def _tier_one() -> list[Variant]:
    variants = []
    for design in DESIGNS:
        for index, product in enumerate(PRODUCTS):
            if len(variants) >= 12:
                break
            label_id = f"t1-clean-{design.name}-{index + 1}"
            variants.append(
                variant(
                    label_id,
                    1,
                    f"Fully compliant {product['class_type']}, {design.name} design.",
                    spec=_spec_from(product, label_id, design=design),
                    application=dict(product),
                )
            )
    return variants


# --- Tier 2 — single-field violations -----------------------------------------


def _tier_two() -> list[Variant]:
    def spirits(
        label_id: str,
        notes: str,
        deviations: dict[str, str],
        *,
        spec_changes: dict[str, object] | None = None,
        app_changes: dict[str, str | None] | None = None,
        **kwargs: object,
    ) -> Variant:
        return variant(
            label_id,
            2,
            notes,
            spec=_spec_from(OLD_TOM, label_id, **(spec_changes or {})),
            application={**OLD_TOM, **(app_changes or {})},
            deviations=deviations,
            **kwargs,
        )

    return [
        # Brand name — 5
        spirits(
            "t2-brand-different",
            "Label brands a different distillery than the application.",
            {"brand_name": "fail"},
            spec_changes={"brand": "IRON GATE DISTILLERY"},
        ),
        spirits(
            "t2-brand-typo",
            "One letter doubled: a plausible transcription slip either way.",
            {"brand_name": "needs_review"},
            spec_changes={"brand": "OLD TOMM DISTILLERY"},
        ),
        spirits(
            "t2-brand-case-only",
            "Dave Morrison's example: STONE'S THROW against Stone's Throw. Not a "
            "violation, and a tool that calls it one gets ignored.",
            {},
            spec_changes={"brand": "STONE'S THROW"},
            app_changes={"brand_name": "Stone's Throw"},
        ),
        spirits(
            "t2-brand-missing",
            "No brand name anywhere on the artwork.",
            {"brand_name": "fail"},
            spec_changes={"brand": None},
        ),
        spirits(
            "t2-brand-corporate-suffix",
            "Label carries the longer legal name. Same business, a judgment call.",
            {"brand_name": "needs_review"},
            spec_changes={"brand": "OLD TOM DISTILLERY CO."},
        ),
        # Class or type — 3
        spirits(
            "t2-class-different",
            "Label says Tennessee Whiskey; the application says Kentucky Straight "
            "Bourbon. Different class designations.",
            {"class_type": "fail"},
            spec_changes={"class_type": "Tennessee Whiskey"},
        ),
        spirits(
            "t2-class-missing",
            "No class or type designation on the label.",
            {"class_type": "fail"},
            spec_changes={"class_type": None},
        ),
        spirits(
            "t2-class-case-only",
            "Set in capitals on the artwork. Formatting, not a discrepancy.",
            {},
            spec_changes={"class_type": "KENTUCKY STRAIGHT BOURBON WHISKEY"},
        ),
        # Alcohol content — 5
        spirits(
            "t2-abv-different",
            "Label states 40%; the application declares 45%.",
            {"alcohol_content": "fail"},
            spec_changes={"alcohol_content": "40% Alc./Vol. (80 Proof)"},
        ),
        spirits(
            "t2-abv-small-difference",
            "0.2 points apart. Inside the 27 CFR 5.65 liquid tolerance, which does "
            "not govern two documents, so a human decides.",
            {"alcohol_content": "needs_review"},
            spec_changes={"alcohol_content": "45.2% Alc./Vol."},
        ),
        spirits(
            "t2-abv-proof-mismatch",
            "45% printed with 80 proof. The label contradicts itself: 27 CFR 5.1 "
            "defines proof as twice the percentage.",
            {"alcohol_content": "fail"},
            spec_changes={"alcohol_content": "45% Alc./Vol. (80 Proof)"},
        ),
        spirits(
            "t2-abv-missing",
            "No alcohol content on the label at all.",
            {"alcohol_content": "fail"},
            spec_changes={"alcohol_content": None},
        ),
        spirits(
            "t2-abv-proof-only",
            "Proof stated without the percentage by volume that 27 CFR 5.65 requires.",
            {"alcohol_content": "fail"},
            spec_changes={"alcohol_content": "90 Proof"},
        ),
        # Net contents — 4
        spirits(
            "t2-volume-different",
            "700 mL on the label against 750 mL on the application.",
            {"net_contents": "fail"},
            spec_changes={"net_contents": "700 mL"},
        ),
        spirits(
            "t2-volume-centilitres",
            "75 cL is 750 mL. 27 CFR 5.70 permits the alternate metric statement.",
            {},
            spec_changes={"net_contents": "75 cL"},
        ),
        spirits(
            "t2-volume-litres",
            "0.75 L is 750 mL.",
            {},
            spec_changes={"net_contents": "0.75 L"},
        ),
        spirits(
            "t2-volume-missing",
            "No net contents statement on the label.",
            {"net_contents": "fail"},
            spec_changes={"net_contents": None},
        ),
        # Bottler name and address — 3
        spirits(
            "t2-bottler-different-city",
            "Label bottled in Frankfort; the application says Bardstown.",
            {"bottler_address": "fail"},
            spec_changes={"bottler": "Bottled by Old Tom Distillery, Frankfort, Kentucky"},
        ),
        spirits(
            "t2-bottler-missing",
            "No name and address of the bottler on the label.",
            {"bottler_address": "fail"},
            spec_changes={"bottler": None},
        ),
        spirits(
            "t2-bottler-abbreviated-state",
            "KY for Kentucky. Almost certainly the same address, still a judgment call.",
            {"bottler_address": "needs_review"},
            spec_changes={"bottler": "Bottled by Old Tom Distillery, Bardstown, KY"},
        ),
        # Government warning — 8, the most coverage of any field
        spirits(
            "t2-warning-verbatim",
            "Control: the statutory text of 27 CFR 16.21, exactly.",
            {},
        ),
        spirits(
            "t2-warning-title-case",
            "'Government Warning' in title case. 27 CFR 16.22 requires capitals — "
            "the violation Jenny Park caught by eye.",
            {"government_warning": "fail"},
            spec_changes={
                "warning": GOVERNMENT_WARNING.replace(WARNING_PREFIX, "Government Warning")
            },
        ),
        spirits(
            "t2-warning-one-word-altered",
            "'birth defects' rendered as 'birth defect'. One word, and the statement "
            "is no longer the statutory one.",
            {"government_warning": "fail"},
            spec_changes={"warning": GOVERNMENT_WARNING.replace("birth defects", "birth defect")},
        ),
        spirits(
            "t2-warning-missing",
            "No government warning anywhere on the label.",
            {"government_warning": "fail"},
            spec_changes={"warning": None},
        ),
        spirits(
            "t2-warning-paraphrased",
            "Same meaning, rewritten. 27 CFR 16.21 is not a summary requirement.",
            {"government_warning": "fail"},
            spec_changes={
                "warning": (
                    "GOVERNMENT WARNING: (1) The Surgeon General says women should not "
                    "drink alcohol while pregnant because of the risk of birth defects. "
                    "(2) Drinking alcohol impairs your ability to drive a car or operate "
                    "machinery and may cause health problems."
                )
            },
        ),
        spirits(
            "t2-warning-not-bold",
            "Prefix set at the same weight as the body text. 27 CFR 16.22 requires bold.",
            {"government_warning": "fail"},
            spec_changes={"warning_bold_prefix": False},
            requires_layout=True,
        ),
        spirits(
            "t2-warning-too-small",
            "Warning at 40% of body-text height — 'burying it in tiny text'.",
            {"government_warning": "fail"},
            spec_changes={"warning_scale": 0.4},
            requires_layout=True,
        ),
        spirits(
            "t2-warning-low-contrast",
            "Warning printed in a grey barely separable from its background.",
            {"government_warning": "fail"},
            spec_changes={"warning_colour": "#b8b5ad", "warning_bg": "#c9c6be"},
            requires_layout=True,
        ),
    ]


# --- Tier 3 — conditional rules ------------------------------------------------
#
# Wine and malt. These are the labels a hardcoded spirits engine gets wrong, so
# they are rendered now even though the rule sets that score them are Phase 4.

_WINE_APPLICATION = {
    "brand_name": "CEDAR HOLLOW",
    "class_type": "California Table Wine",
    "alcohol_content": None,
    "net_contents": "750 mL",
    "bottler_address": "Bottled by Cedar Hollow Cellars, Napa, California",
}

_MALT_APPLICATION = {
    "brand_name": "NORTH SHORE BREWING",
    "class_type": "India Pale Ale",
    "alcohol_content": None,
    "net_contents": "355 mL",
    "bottler_address": "Brewed and bottled by North Shore Brewing, Duluth, Minnesota",
}

_PHASE_FOUR = "Wine and malt rule sets ship in Phase 4 (docs/PRD.md → Sequencing)."


def _tier_three() -> list[Variant]:
    def conditional(
        label_id: str,
        beverage_type: str,
        base: dict[str, str | None],
        notes: str,
        deviations: dict[str, str],
        *,
        spec_changes: dict[str, object] | None = None,
        app_changes: dict[str, str | None] | None = None,
    ) -> Variant:
        product = {**base, **(app_changes or {})}
        spec = _spec_from(product, label_id, design=MODERN, **(spec_changes or {}))
        return variant(
            label_id,
            3,
            notes,
            spec=spec,
            application=product,
            deviations=deviations,
            beverage_type=beverage_type,
            scored=False,
            excluded_reason=_PHASE_FOUR,
        )

    return [
        conditional(
            "t3-wine-table-wine-no-abv",
            "wine",
            _WINE_APPLICATION,
            "12% table wine with no percentage stated. 27 CFR 4.36 permits the "
            "omission when the label says 'table wine' — an engine that requires "
            "ABV rejects a valid label.",
            {},
        ),
        conditional(
            "t3-wine-over-14-abv-present",
            "wine",
            _WINE_APPLICATION,
            "15.5% wine stating its alcohol content, as 27 CFR 4.36 requires above 14%.",
            {},
            app_changes={
                "class_type": "Napa Valley Cabernet Sauvignon",
                "alcohol_content": "15.5% Alc./Vol.",
            },
        ),
        conditional(
            "t3-wine-over-14-abv-missing",
            "wine",
            _WINE_APPLICATION,
            "15.5% wine with no alcohol statement. Above 14% the omission is a "
            "violation, and 'table wine' does not save it.",
            {"alcohol_content": "fail"},
            app_changes={
                "class_type": "Napa Valley Cabernet Sauvignon",
                "alcohol_content": "15.5% Alc./Vol.",
            },
            spec_changes={"alcohol_content": None},
        ),
        conditional(
            "t3-malt-plain-no-abv",
            "malt",
            _MALT_APPLICATION,
            "An ordinary IPA with no alcohol statement. 27 CFR 7.63 requires none.",
            {},
        ),
        conditional(
            "t3-malt-added-flavors-abv-present",
            "malt",
            _MALT_APPLICATION,
            "Flavored malt beverage stating its alcohol content, as 27 CFR 7.63 "
            "requires once alcohol comes from added nonbeverage ingredients.",
            {},
            app_changes={
                "class_type": "Flavored Malt Beverage",
                "alcohol_content": "8% Alc./Vol.",
            },
        ),
        conditional(
            "t3-malt-added-flavors-abv-missing",
            "malt",
            _MALT_APPLICATION,
            "Flavored malt beverage with no alcohol statement — the case where "
            "27 CFR 7.63 does require one.",
            {"alcohol_content": "fail"},
            app_changes={
                "class_type": "Flavored Malt Beverage",
                "alcohol_content": "8% Alc./Vol.",
            },
            spec_changes={"alcohol_content": None},
        ),
    ]


# --- Tier 4 — image quality ----------------------------------------------------
#
# Half degraded-but-readable, half genuinely unreadable. Testing only the
# readable half rewards a tool that hallucinates confidently from mud.

DEGRADED_READABLE = (
    ("blur-light", "Slight focus miss, still legible."),
    ("low-light", "Underexposed photograph."),
    ("skew", "Photographed at an angle."),
    ("glare-mild", "Reflection across the upper label, text still readable."),
    ("jpeg-artefacts", "Heavily recompressed phone photo."),
    ("downscale", "Small but legible: 550px wide."),
)

DEGRADED_UNREADABLE = (
    ("blur-heavy", "Out of focus beyond recovery."),
    ("glare-severe", "Reflection covers the lower third, including the warning."),
    ("tiny", "400px wide. Text this small cannot be read reliably."),
    ("near-black", "Photographed in the dark."),
    ("skew-crop", "Steep angle with the bottom of the label out of frame."),
    ("noise", "Sensor noise swamping the text."),
)


def _tier_four() -> list[Variant]:
    variants = []
    for name, notes in DEGRADED_READABLE:
        label_id = f"t4-{name}"
        variants.append(
            variant(
                label_id,
                4,
                f"{notes} Must still be read correctly.",
                spec=_spec_from(OLD_TOM, label_id),
                application=dict(OLD_TOM),
                degradation=name,
            )
        )
    for name, notes in DEGRADED_UNREADABLE:
        label_id = f"t4-{name}"
        variants.append(
            variant(
                label_id,
                4,
                f"{notes} Must fail with a specific reason, not a generic error.",
                spec=_spec_from(OLD_TOM, label_id),
                application=dict(OLD_TOM),
                unreadable=True,
                degradation=name,
            )
        )
    return variants


# --- Tier 5 — same field of vision --------------------------------------------


def _tier_five() -> list[Variant]:
    cases = (
        ("alcohol_content", "Alcohol content moved to the back label."),
        ("class_type", "Class designation moved to the back label."),
        ("brand", "Brand name printed only on the back label."),
    )
    variants = []
    for index, (moved, notes) in enumerate(cases, start=1):
        label_id = f"t5-field-of-vision-{index}"
        variants.append(
            variant(
                label_id,
                5,
                f"{notes} 27 CFR 5.63 requires brand, class/type and alcohol "
                "content in the same field of vision.",
                spec=_spec_from(OLD_TOM, label_id, back_fields=(moved,), design=COMPACT),
                application=dict(OLD_TOM),
                deviations={"government_warning": "fail"},
                requires_layout=True,
            )
        )
    return variants


CATALOGUE: list[Variant] = [
    *_tier_one(),
    *_tier_two(),
    *_tier_three(),
    *_tier_four(),
    *_tier_five(),
]


# --- Tier 6 — batch throughput fixture ----------------------------------------


def batch_variants(count: int = 200, seed: int = 20260809) -> list[Variant]:
    """Permutations of tiers 2-3, for throughput only.

    Not scored for accuracy: this fixture answers "do 200 labels complete with
    visible progress", which is a different question from "is the verdict right".
    """
    rng = random.Random(seed)
    source = [v for v in CATALOGUE if v.tier in (2, 3)]
    variants = []
    for index in range(count):
        base = source[index % len(source)]
        label_id = f"t6-batch-{index + 1:03d}"
        spec = LabelSpec(**{**vars(base.spec), "label_id": label_id})
        spec.design = rng.choice(DESIGNS)
        variants.append(
            Variant(
                label_id=label_id,
                tier=6,
                beverage_type=base.beverage_type,
                spec=spec,
                application=dict(base.application),
                expected_fields=dict(base.expected_fields),
                expected_overall=base.expected_overall,
                notes=f"Batch throughput fixture, permuted from {base.label_id}.",
                scored=False,
                excluded_reason="Throughput fixture; accuracy is scored on tiers 1-5.",
                requires_layout=base.requires_layout,
            )
        )
    return variants


# --- Tier 7 — malformed manifests ---------------------------------------------
#
# Every one of these must be caught in the pre-flight summary, before a
# four-minute run, and named with its filename or row number
# (docs/ui-spec.md → Screen 4).

MALFORMED_MANIFESTS: tuple[tuple[str, str, str], ...] = (
    (
        "missing-image.csv",
        "A manifest row naming an image that was not uploaded.",
        "application_id,image,brand_name,class_type,alcohol_content,net_contents,"
        "bottler_address\n"
        "APP-1001,not-uploaded.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,"
        '45% Alc./Vol. (90 Proof),750 mL,"Bottled by Old Tom Distillery, Bardstown, Kentucky"\n',
    ),
    (
        "orphan-image.csv",
        "An uploaded image with no matching manifest row.",
        "application_id,image,brand_name,class_type,alcohol_content,net_contents,bottler_address\n",
    ),
    (
        "bad-row.csv",
        "A row with fewer columns than the header declares.",
        "application_id,image,brand_name,class_type,alcohol_content,net_contents,"
        "bottler_address\n"
        "APP-1002,t1-clean-classic-1.png,OLD TOM DISTILLERY\n",
    ),
    (
        "wrong-columns.csv",
        "A manifest with the wrong column names entirely.",
        "id,file,name,strength\nAPP-1003,t1-clean-classic-1.png,OLD TOM,45\n",
    ),
)


# --- Degradation ---------------------------------------------------------------


def _apply_degradation(image: Image.Image, kind: str) -> Image.Image:
    """Damage an image the way a real submission gets damaged."""
    if kind == "blur-light":
        return image.filter(ImageFilter.GaussianBlur(1.6))
    if kind == "low-light":
        return ImageEnhance.Brightness(image).enhance(0.42)
    if kind == "skew":
        return image.rotate(6, expand=True, fillcolor="#d8d4cc", resample=Image.BICUBIC)
    if kind == "glare-mild":
        return _glare(image, top=0.05, bottom=0.35, opacity=110)
    if kind == "jpeg-artefacts":
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=18)
        buffer.seek(0)
        return Image.open(buffer).convert("RGB")
    if kind == "downscale":
        return image.resize((550, int(550 * image.height / image.width)), Image.LANCZOS)
    if kind == "blur-heavy":
        return image.filter(ImageFilter.GaussianBlur(11))
    if kind == "glare-severe":
        return _glare(image, top=0.52, bottom=1.05, opacity=253)
    if kind == "tiny":
        return image.resize((400, int(400 * image.height / image.width)), Image.LANCZOS)
    if kind == "near-black":
        return ImageEnhance.Brightness(image).enhance(0.06)
    if kind == "skew-crop":
        rotated = image.rotate(34, expand=True, fillcolor="#2b2b2b", resample=Image.BICUBIC)
        return rotated.crop((0, 0, rotated.width, int(rotated.height * 0.55)))
    if kind == "noise":
        noise = Image.effect_noise((image.width, image.height), 190).convert("RGB")
        return Image.blend(image, noise, 0.72)
    raise ValueError(f"unknown degradation {kind!r}")


def _glare(image: Image.Image, *, top: float, bottom: float, opacity: int) -> Image.Image:
    """A bright reflection across part of the label."""
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse(
        [
            -image.width * 0.2,
            image.height * top,
            image.width * 1.2,
            image.height * bottom,
        ],
        fill=(255, 255, 255, opacity),
    )
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


# --- Writing -------------------------------------------------------------------


def _render(variants: list[Variant], out_dir: Path) -> None:
    for item in variants:
        path = render(item.spec, out_dir)
        if item.degradation:
            image = Image.open(path)
            _apply_degradation(image, item.degradation).save(path)


def _as_fixture(item: Variant) -> dict[str, object]:
    return {
        "id": item.label_id,
        "tier": item.tier,
        "beverage_type": item.beverage_type,
        "image": item.image_name,
        "notes": item.notes,
        "scored": item.scored,
        "excluded_reason": item.excluded_reason or None,
        "requires_layout": item.requires_layout,
        "degradation": item.degradation,
        "application": item.application,
        "expected_fields": item.expected_fields,
        "expected_overall": item.expected_overall,
    }


def write_expectations(variants: list[Variant], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_from": "corpus/generate.py",
        "statutory_warning": GOVERNMENT_WARNING,
        "curated_count": sum(1 for v in variants if v.tier <= 5),
        "scored_count": sum(1 for v in variants if v.scored),
        "labels": [_as_fixture(v) for v in variants],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_batch_manifest(variants: list[Variant], path: Path) -> None:
    """The CSV an agent would upload alongside 200 images."""
    columns = [
        "application_id",
        "image",
        "beverage_type",
        "brand_name",
        "class_type",
        "alcohol_content",
        "net_contents",
        "bottler_address",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [",".join(columns)]
    for index, item in enumerate(variants, start=1):
        values = [
            f"APP-{index + 10000}",
            item.image_name,
            item.beverage_type,
            *[item.application.get(name) or "" for name in columns[3:]],
        ]
        rows.append(",".join(f'"{value}"' for value in values))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_malformed_manifests(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, _notes, content in MALFORMED_MANIFESTS:
        (directory / name).write_text(content, encoding="utf-8")
    (directory / "README.md").write_text(
        "# Malformed manifests (tier 7)\n\n"
        "Each must be caught in the pre-flight summary and named with its "
        "filename or row number, before any processing starts.\n\n"
        + "".join(f"- `{name}` — {notes}\n" for name, notes, _ in MALFORMED_MANIFESTS),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="render every curated tier")
    parser.add_argument("--tier", type=int, help="render one tier (1-5)")
    parser.add_argument("--id", dest="label_id", help="render one label by id")
    parser.add_argument(
        "--batch", type=int, metavar="N", help="render the N-label throughput fixture"
    )
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    if args.batch:
        variants = batch_variants(args.batch)
        _render(variants, args.out / "batch")
        write_batch_manifest(variants, FIXTURES / "batch" / "manifest.csv")
        print(f"{len(variants)} batch labels -> {args.out / 'batch'}")
        return 0

    if args.label_id:
        selected = [v for v in CATALOGUE if v.label_id == args.label_id]
        if not selected:
            parser.error(f"no label with id {args.label_id!r}")
    elif args.tier:
        selected = [v for v in CATALOGUE if v.tier == args.tier]
    elif args.all:
        selected = CATALOGUE
    else:
        parser.error("choose --all, --tier, --id or --batch")

    _render(selected, args.out)
    if args.all:
        write_expectations(CATALOGUE, FIXTURES / "expected.json")
        write_malformed_manifests(FIXTURES / "manifests")
    print(f"{len(selected)} labels -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
