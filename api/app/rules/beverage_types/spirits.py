"""Distilled spirits label requirements — 27 CFR part 5.

Verified against Cornell LII on 2026-08-09.

§5.63 splits the mandatory information in two. Brand name, class or type, and
alcohol content must appear **in the same field of vision** — one side of the
container, viewable at once. Name and address and net contents must appear on
the container but may be anywhere on it.
"""

from __future__ import annotations

from app.rules.beverage_types.base import (
    BeverageRules,
    FieldRule,
    Matcher,
    Requirement,
)

SPIRITS = BeverageRules(
    beverage_type="spirits",
    display_name="Distilled spirits",
    citation="27 CFR part 5",
    checks_field_of_vision=True,
    available=True,
    fields=(
        FieldRule(
            field="brand_name",
            display_name="Brand name",
            matcher=Matcher.TEXT,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 5.63(a), 5.64",
        ),
        FieldRule(
            field="class_type",
            display_name="Class or type",
            matcher=Matcher.TEXT,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 5.63(a)",
        ),
        FieldRule(
            field="alcohol_content",
            display_name="Alcohol content",
            matcher=Matcher.ABV,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 5.63(a), 5.65",
        ),
        FieldRule(
            field="net_contents",
            display_name="Net contents",
            matcher=Matcher.VOLUME,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 5.63(b), 5.70",
        ),
        FieldRule(
            field="bottler_address",
            display_name="Bottler or producer name and address",
            matcher=Matcher.TEXT,
            requirement=Requirement.REQUIRED,
            citation="27 CFR 5.63(b), 5.66",
        ),
        FieldRule(
            field="country_of_origin",
            display_name="Country of origin",
            matcher=Matcher.ORIGIN,
            requirement=Requirement.CONDITIONAL,
            citation="27 CFR 5.69",
            condition="Required on imported spirits only.",
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
