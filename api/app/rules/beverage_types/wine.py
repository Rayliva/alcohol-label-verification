"""Wine label requirements — 27 CFR part 4.

Verified against Cornell LII on 2026-08-09.

**Declared, not yet shipped.** The field list and its conditional are recorded
here from the first commit so the engine's shape is right; the corpus labels and
the tuning that make wine trustworthy are Phase 4 (PRD → Sequencing). Until then
`available=False` and the UI disables the option with the reason below.

The conditional is the whole point of doing this as configuration. §4.36 lets
wine at 14% alcohol or less omit the percentage entirely when the label states
"table wine" or "light wine". An engine that treats alcohol content as
unconditionally required would reject a perfectly valid table wine label.
"""

from __future__ import annotations

from app.rules.beverage_types.base import (
    BeverageRules,
    FieldRule,
    Matcher,
    Requirement,
)

WINE = BeverageRules(
    beverage_type="wine",
    display_name="Wine",
    citation="27 CFR part 4",
    checks_field_of_vision=False,
    available=False,
    unavailable_reason="Wine checking is coming next. Distilled spirits work today.",
    fields=(
        FieldRule(
            field="brand_name",
            display_name="Brand name",
            matcher=Matcher.TEXT,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 4.32(a), 4.33",
        ),
        FieldRule(
            field="class_type",
            display_name="Class or type",
            matcher=Matcher.TEXT,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 4.32(a), 4.34",
        ),
        FieldRule(
            field="alcohol_content",
            display_name="Alcohol content",
            matcher=Matcher.ABV,
            requirement=Requirement.CONDITIONAL,
            citation="27 CFR 4.32(b), 4.36",
            condition=(
                "Wine at 14% alcohol or less may omit the percentage if the label says "
                '"table wine" or "light wine". Above 14% it is required.'
            ),
        ),
        FieldRule(
            field="net_contents",
            display_name="Net contents",
            matcher=Matcher.VOLUME,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 4.32(b), 4.37",
        ),
        FieldRule(
            field="bottler_address",
            display_name="Bottler or importer name and address",
            matcher=Matcher.TEXT,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 4.32(b), 4.35",
        ),
        FieldRule(
            field="country_of_origin",
            display_name="Country of origin",
            matcher=Matcher.ORIGIN,
            requirement=Requirement.CONDITIONAL,
            citation="27 CFR 4.32",
            condition="Required on imported wine only.",
        ),
        FieldRule(
            field="government_warning",
            display_name="Government warning",
            matcher=Matcher.WARNING,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 16.21, 16.22",
        ),
    ),
)
