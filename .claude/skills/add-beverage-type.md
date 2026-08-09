# Add or edit a beverage-type rule set

## When to use

Changing which fields are required for spirits, wine, or malt beverages — or adding a new category.

## The principle

Beverage types are **configuration, not code paths**. `api/app/rules/beverage_types/` holds a declarative rule set per type; the engine reads it. If adding a beverage type requires an `if beverage_type == ...` branch in the engine, the abstraction has leaked and should be fixed rather than worked around.

This matters because the requirements genuinely differ, and a spirits-shaped engine emits false violations on two of three categories.

## Current rule sets

| Field | Spirits (Pt. 5) | Wine (Pt. 4) | Malt (Pt. 7) |
|---|---|---|---|
| Brand name | Required | Required | Required |
| Class/type | Required | Required | Required |
| Alcohol content | Required | **Conditional** | **Conditional** |
| Net contents | Required | Required | Required |
| Bottler/importer name & address | Required | Required | Required |
| Government warning | Required | Required | Required |

**The conditionals are the whole reason this is config:**

- **Wine ≤ 14% ABV** may omit the percentage if the label states "table wine" or "light wine". Above 14%, mandatory.
- **Malt beverages** require ABV only when alcohol derives from added nonbeverage flavors or ingredients.

## Steps

1. **Verify against the CFR.** Cite the section; do not write the rule from memory.
2. Edit or add the rule set in `api/app/rules/beverage_types/<type>.py`. Express conditionals declaratively — a predicate over `LabelData`, not imperative branching in the engine.
3. Add unit tests in `api/tests/unit/rules/` covering the conditional **in both directions** — the case where the field is required and the case where its absence is legal.
4. Add corpus labels for both directions (tier 3).
5. Run the accuracy suite.

## Common pitfalls

- **Testing only the failing direction.** "Wine over 14% with no ABV → FAIL" without "wine under 14% labeled table wine with no ABV → PASS" leaves the more damaging bug — a false violation — untested.
- **Treating a conditional as a warning.** If the omission is legal, the verdict is PASS, not NEEDS REVIEW. Flagging legal labels erodes exactly the trust the product depends on.
- **Adding an engine branch.** If you cannot express the rule declaratively, change the rule-set schema — don't special-case it in the engine.
- **Assuming the sample label generalizes.** The brief's example is distilled spirits. It is one of three.
