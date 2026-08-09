"""Malt beverage label requirements — 27 CFR part 7.

Verified against Cornell LII on 2026-08-09.

**Declared, not yet shipped** — see wine.py for the reasoning. Phase 4.

§7.63 lists five mandatory items, and its alcohol content requirement is
narrower than either of the other two categories: it applies only to malt
beverages "containing any alcohol derived from added nonbeverage flavors or
other added nonbeverage ingredients (other than hops extract) containing
alcohol". An ordinary beer needs no alcohol statement at all, so demanding one
would flag most of the category.
"""

from __future__ import annotations

from app.rules.beverage_types.base import (
    BeverageRules,
    FieldRule,
    Matcher,
    Requirement,
)

MALT = BeverageRules(
    beverage_type="malt",
    display_name="Malt beverage",
    citation="27 CFR part 7",
    checks_field_of_vision=False,
    available=False,
    unavailable_reason=("Malt beverage checking is coming next. Distilled spirits work today."),
    fields=(
        FieldRule(
            field="brand_name",
            display_name="Brand name",
            matcher=Matcher.TEXT,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 7.63(a), 7.64",
        ),
        FieldRule(
            field="class_type",
            display_name="Class or type",
            matcher=Matcher.TEXT,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 7.63(a)",
        ),
        FieldRule(
            field="alcohol_content",
            display_name="Alcohol content",
            matcher=Matcher.ABV,
            requirement=Requirement.CONDITIONAL,
            citation="27 CFR 7.63(a), 7.65",
            condition=(
                "Required only when the alcohol comes from added nonbeverage "
                "flavors or ingredients. An ordinary beer needs no statement."
            ),
        ),
        FieldRule(
            field="net_contents",
            display_name="Net contents",
            matcher=Matcher.VOLUME,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 7.63(a), 7.70",
        ),
        FieldRule(
            field="bottler_address",
            display_name="Bottler or importer name and address",
            matcher=Matcher.TEXT,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 7.63(a), 7.66",
        ),
        FieldRule(
            field="country_of_origin",
            display_name="Country of origin",
            matcher=Matcher.TEXT,
            requirement=Requirement.CONDITIONAL,
            citation="27 CFR 7.63",
            condition="Required on imported malt beverages only.",
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
