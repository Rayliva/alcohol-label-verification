# Verify regulations against source

Never write a regulatory citation, threshold, or required text from memory.

## The rule

1. **Every compliance rule cites its CFR section** in a docstring:

   ```python
   def check_net_contents(label: LabelData) -> FieldResult:
       """Verify net contents per 27 CFR 5.70."""
   ```

2. **Every citation is verified against a primary source** before use — eCFR, Cornell LII, or ttb.gov. Not a blog post, not model memory, not another file in this repo.

3. **Statutory text is copied, never retyped.** The government warning (27 CFR 16.21) must be byte-exact.

4. **When a source cannot be reached, say so** and mark the value `TODO: unverified`. Do not fill the gap with a plausible number.

## Why

This tool renders compliance verdicts. A hallucinated threshold or a single wrong word in the warning text produces confident, authoritative, wrong answers — and the wrongness is invisible, because the output looks exactly like a correct one. Every other bug in this system announces itself; this class does not.

## Verified reference

Confirmed against Cornell LII, 2026-08-09:

| Item | Section | Value |
|---|---|---|
| Warning text | 16.21 | One continuous statement, `(1)` and `(2)` inline |
| `GOVERNMENT WARNING` | 16.22 | Capital letters **and** bold |
| Type size | 16.22 | ≤237 mL: 1 mm · >237 mL–3 L: 2 mm · >3 L: 3 mm |
| Max chars/inch | 16.22 | 40 / 25 / 12 respectively |
| Spirits mandatory fields | 5.63 | Brand, class/type, ABV same field of vision |
| Spirits ABV tolerance | 5.65 | ±0.3 points — **label vs actual liquid, not form vs label** |
| Wine ABV | 4.36 | Optional ≤14% if "table wine"/"light wine"; ±1.5 / ±1.0 tolerance |
| Malt ABV | 7.63 | Required only with added nonbeverage alcohol |

Confirmed against Cornell LII, 2026-08-11:

| Item | Section | Value |
|---|---|---|
| Country of origin | 27 CFR 5.69 | **States no requirement.** Its entire text is a cross-reference: "For U.S. Customs and Border Protection (CBP) rules regarding country of origin marking requirements, see the CBP regulations at 19 CFR parts 102 and 134." Citing 5.69 alone as the source of the requirement is misleading |
| Country of origin marking | 19 CFR 134.11 | "every article of foreign origin (or its container) imported into the United States shall be marked in a conspicuous place as legibly, indelibly, and permanently as the nature of the article (or container) will permit" — in the English name of the country of origin. Exceptions exist under section 304, Tariff Act of 1930, and are not enumerated there |

## Examples

**Do** — verify before implementing, and record the date:

> Confirmed 27 CFR 16.22 type sizes against Cornell LII on 2026-08-09.

**Don't** — write a threshold that "sounds right":

```python
MIN_WARNING_TYPE_MM = 1.5  # no such threshold exists
```

**Don't** — apply a tolerance outside its scope. The ABV tolerances govern label vs. the liquid in the bottle, lab-verified. Application and label are both documents and should agree exactly.
