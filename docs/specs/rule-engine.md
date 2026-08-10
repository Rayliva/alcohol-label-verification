# Spec — Compliance rule engine (spirits)

**Status:** approved for build, Phase 1
**Date:** 2026-08-09
**Traces to:** `requirements.md` (label field matching, exact warning check, "judgment" over binary pass/fail) · `docs/PRD.md` FR-3, FR-5, FR-6, FR-7, FR-13, P2-13
**Implements:** `api/app/rules/`

---

## 1. What this is

`app/rules/` takes two documents — what the COLA application **declared** and what was
**detected** on the artwork — plus a small set of geometric measurements, and returns one
`FieldResult` per required field, a list of government-warning sub-checks, and a single
label-level outcome.

It is pure. It imports nothing from `ocr/` or `extraction/`, performs no I/O, and has no
notion of images, HTTP, or models. Its input is data; its output is verdicts.

**The tool advises; the agent decides.** No verdict here is authoritative. Every one of them
carries a plain sentence a compliance agent can act on.

---

## 2. Inputs and outputs

### 2.1 Input

```python
Application      # what the form says   — all fields str | None
LabelObservation # what the label says  — detected fields + optional layout metrics
BeverageRules    # config: which fields are required, and under what condition
```

`LabelObservation.layout` is `LayoutMetrics | None`. It carries facts only an image can
supply — warning text height, median body-text height, stroke-weight ratio, contrast ratio,
and which side of the container each field appeared on. It is **optional by design**: the
text checks must run without it, and every geometric check degrades to `NEEDS_REVIEW`
with a reason naming the missing measurement rather than silently passing.

### 2.2 Output

```python
LabelReport(
    beverage_type: str,
    fields: tuple[FieldResult, ...],          # one per required field, in display order
    warning_checks: tuple[WarningCheck, ...], # the six sub-checks
    overall: Verdict,                         # pass | needs_review | fail
)
```

`unreadable` is a fourth **label-level** outcome, but it is produced upstream by the
pipeline, never by this package. If the rule engine ran at all, the image was readable.
See PRD FR-3 and `.claude/rules/error-handling.md` — a verdict means the check ran.

`overall` is the worst verdict among `fields` and `warning_checks`. Worst wins: any FAIL
makes the label FAIL; otherwise any NEEDS_REVIEW makes it NEEDS_REVIEW.

---

## 3. Behaviour

### 3.1 Alcohol content — `match_abv.py`

Verified against Cornell LII on 2026-08-09: **27 CFR 5.65** (alcohol content statement,
±0.3 point tolerance) and **27 CFR 5.1** ("*Proof:* the ethyl alcohol content of a liquid at
60 degrees Fahrenheit, stated as twice the percentage of ethyl alcohol by volume").

**Parsing.** From free text, recover a percentage and an optional proof figure:

| Input | ABV | Proof |
|---|---|---|
| `45% Alc./Vol. (90 Proof)` | 45.0 | 90.0 |
| `ALC. 45% BY VOL.` | 45.0 | — |
| `Alcohol 45 percent by volume` | 45.0 | — |
| `40% alc/vol` | 40.0 | — |
| `45.5% Alc/Vol` | 45.5 | — |
| `90 Proof` | — | 90.0 |

A bare number with no `%`, no `percent`, and no `proof` does not parse. Guessing which one
a stray `45` meant is exactly the confident-and-wrong failure this project cannot afford.

**Checks, in order. The first that applies decides the verdict.**

| # | Condition | Verdict | Reason names |
|---|---|---|---|
| 1 | Nothing declared, nothing detected | NEEDS_REVIEW | that both are empty |
| 2 | Declared, absent from label | FAIL | that alcohol content is required for spirits (§5.63) |
| 3 | On the label, not declared | NEEDS_REVIEW | that the application declared nothing |
| 4 | Detected text present but no percentage or proof parses | NEEDS_REVIEW | the text that could not be read |
| 5 | Label states proof only, no percent by volume | FAIL | §5.65 — the percentage statement is mandatory |
| 6 | Label's own proof ≠ 2 × label's own ABV | FAIL | both numbers, and that proof is twice ABV |
| 7 | Declared ABV ≠ detected ABV, difference > 0.3 points | FAIL | both values |
| 8 | Declared ABV ≠ detected ABV, difference ≤ 0.3 points | NEEDS_REVIEW | both values **and** that the ±0.3 tolerance governs label vs liquid, not form vs label |
| 9 | ABV equal, declared proof ≠ detected proof | NEEDS_REVIEW | both proof figures |
| 10 | ABV equal (and proof consistent) | PASS | — |

Check 6 runs before 7 because a label that contradicts itself is a defect in the label
regardless of what the form says.

**The ±0.3 tolerance is never a pass rule.** It governs the labelled figure against the
liquid in the bottle, lab-verified. The application and the label are both documents and
should agree exactly. It appears only as context inside a NEEDS_REVIEW reason, so an agent
who knows the regulation is not confused by a flag on a 0.1-point difference.

Trailing-zero and formatting differences are not differences: `45%`, `45.0%`, and
`45.00% ALC/VOL` are the same number.

### 3.2 Net contents — `match_volume.py`

Verified against Cornell LII on 2026-08-09: **27 CFR 5.70** — "The word 'liter' may be
alternatively spelled 'litre' or may be abbreviated as 'L'"; "milliliters" may be
abbreviated "ml.", "mL.", or "ML."; U.S. customary equivalents and metric equivalents such
as centiliters may also appear.

**Parsing.** Recover a quantity and normalise it to millilitres.

| Unit | mL | Note |
|---|---|---|
| mL, ml, ML, milliliter(s), millilitre(s) | 1 | |
| cL, cl, centiliter(s), centilitre(s) | 10 | |
| dL, deciliter(s) | 100 | |
| L, l, liter(s), litre(s) | 1000 | |
| fl oz, fluid ounce(s) | 29.5735295625 | U.S. customary, exact by definition |
| pt, pint(s) | 473.176473 | |
| qt, quart(s) | 946.352946 | |
| gal, gallon(s) | 3785.411784 | |

A statement may carry both systems — `750 mL (25.4 fl oz)`. The **metric** statement is
authoritative; where both are present the metric one is compared and the other ignored.

**Checks.**

| # | Condition | Verdict |
|---|---|---|
| 1 | Nothing declared, nothing detected | NEEDS_REVIEW |
| 2 | Declared, absent from label | FAIL — net contents is required (§5.63) |
| 3 | On the label, not declared | NEEDS_REVIEW |
| 4 | A number with no unit on either side | NEEDS_REVIEW, naming the unreadable text |
| 5 | Volumes equal within tolerance | PASS |
| 6 | Volumes differ | FAIL, naming both in mL |

**Tolerance.** Both sides metric, or both U.S. customary: 0.1% relative — enough for float
representation, not enough to hide a real difference. Mixed systems: 1% relative, because
`750 mL` and `25.4 fl oz` are the same bottle rounded differently. The reason states the
conversion when it was applied.

`750 mL` = `75 cL` = `0.75 L` = PASS, and the reason says the units differ but the volume
is the same.

### 3.3 Government warning — `warning.py`

Verified against Cornell LII on 2026-08-09: **27 CFR 16.21** (text) and **16.22** (format).

Statutory text, one continuous statement with `(1)` and `(2)` inline:

> GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink
> alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption
> of alcoholic beverages impairs your ability to drive a car or operate machinery, and may
> cause health problems.

**No fuzzy matching anywhere in this module.** Whitespace is normalised — a line break on
artwork is a layout artefact — and nothing else. Case folding here would pass the
title-case violation this product exists to catch.

Six sub-checks. Each returns its own `WarningCheck(check, verdict, reason)`; together they
also produce the single `government_warning` `FieldResult` that appears in `fields`.

| `check` | Rule | FAIL when |
|---|---|---|
| `text_exact` | §16.21 | Text differs from statutory after whitespace normalisation. Reason names the first differing words |
| `caps` | §16.22 | `GOVERNMENT WARNING` is not in capitals — `Government Warning` FAILs |
| `bold` | §16.22 | Prefix stroke-weight ratio below the bold threshold |
| `proportion` | §16.22 (proxy) | Warning height is disproportionately small relative to median body text |
| `contrast` | §16.22 | Warning text does not contrast with its background |
| `field_of_vision` | §5.63 | Brand, class/type and alcohol content are not on one side. Spirits only |

**Absent warning** — every sub-check is FAIL and the reason says the warning was not found,
not that it failed a format rule.

**Thresholds** (provisional, tuned against the corpus, named constants in one place):

Calibrated against the corpus on 2026-08-09; the measured values behind each are
recorded beside the constants in `app/rules/warning.py`.

- `bold`: stroke-thickness ratio ≥ 1.20 PASS · 1.10–1.20 NEEDS_REVIEW · < 1.10 FAIL
  (measured: 1.35 compliant, 1.06 on the unbold variant)
- `proportion`: warning height ≥ 45% of the median height of the other text PASS ·
  30–45% NEEDS_REVIEW · < 30% FAIL (measured: 0.525–0.610 compliant, 0.220 on the
  shrunken variant). This is a **proxy** for §16.22's absolute millimetre sizes,
  which are not derivable from an uncalibrated image (PRD OS-7). The README says
  so plainly.
- `contrast`: WCAG contrast ratio ≥ 4.5 PASS · 3.0–4.5 NEEDS_REVIEW · < 3.0 FAIL
  (measured: 18.6 compliant, 1.2 on the low-contrast variant)

**Missing measurement is never a PASS.** With `layout is None`, `bold`, `proportion`,
`contrast` and `field_of_vision` each return NEEDS_REVIEW naming the measurement that was
unavailable. A geometric check that silently passes when it did not run is a false PASS,
and false PASSes are the error class this product is scored on.

### 3.4 Beverage rules — `beverage_types/`

Config, not code paths. Each beverage type declares its field set:

```python
FieldRule(field, display_name, matcher, requirement)
```

`requirement` is `REQUIRED`, `OPTIONAL`, or a named conditional. Only `spirits.py` is
populated in Phase 1; `wine.py` and `malt.py` exist with their conditionals declared and
are marked unavailable so the UI can disable their buttons with an explanation (PRD
Sequencing; ui-spec resolution 9).

Spirits (§5.63): brand name, class/type, alcohol content, net contents, bottler/producer
name and address — all required; country of origin required for imports only; government
warning required (§16.21).

### 3.5 Engine — `engine.py`

`evaluate(application, observation, rules) -> LabelReport`. Walks the beverage type's field
list in display order, dispatches each to its matcher, appends the warning sub-checks, and
folds the worst verdict into `overall`. Adding a field is a config edit; adding a *kind* of
comparison is a new matcher.

---

## 4. Boundaries — what this does NOT do

- **No image handling.** No decoding, cropping, OCR, or preprocessing. Geometric facts
  arrive pre-measured in `LayoutMetrics`.
- **No absolute type-size verification.** Millimetres are not derivable from an
  uncalibrated image (PRD OS-7). The proportional check ships instead, and the limitation
  is published.
- **No `unreadable` verdict.** That is a pipeline outcome (§2.2).
- **No wine or malt rule content** in Phase 1 — the *shape* is there, the content is Phase 4.
- **No standards of fill.** §5.203 constrains which container sizes may be sold. The brief
  asks whether the label matches the application, not whether the bottle is a legal size.
- **No persistence, no overrides.** An override is a UI act recorded alongside a result,
  never a mutation of one.

---

## 5. Acceptance criteria

1. Given declared `45% Alc./Vol. (90 Proof)` and detected `45% ALC/VOL (90 PROOF)`, the
   alcohol content verdict is PASS.
2. Given declared `45% Alc./Vol. (90 Proof)` and detected `45% Alc./Vol. (80 Proof)`, the
   verdict is FAIL and the reason names 90 and 45.
3. Given declared `45%` and detected `45.2%`, the verdict is NEEDS_REVIEW and the reason
   states the ±0.3 tolerance does not apply between form and label.
4. Given declared `45%` and detected `40%`, the verdict is FAIL.
5. Given declared `750 mL` and detected `75 cL`, the verdict is PASS.
6. Given declared `750 mL` and detected `700 mL`, the verdict is FAIL and the reason names
   both volumes.
7. Given a label whose warning reads `Government Warning: (1) According to…`, `caps` is
   FAIL, its reason contains "capital letters", and `text_exact` is also FAIL.
8. Given the statutory text broken across three lines, `text_exact` is PASS.
9. Given the statutory text with "birth defects" changed to "birth defect", `text_exact` is
   FAIL and the reason names the difference.
10. Given no warning on the label, all six sub-checks are FAIL and the government warning
    `FieldResult` reason says it was not found.
11. Given `layout is None`, `bold`, `proportion`, `contrast` and `field_of_vision` are each
    NEEDS_REVIEW, never PASS.
12. Given every field matching and a verbatim warning, `overall` is PASS.
13. Given one field NEEDS_REVIEW and the rest PASS, `overall` is NEEDS_REVIEW.
14. Given one field FAIL and one NEEDS_REVIEW, `overall` is FAIL.
15. `rules/` imports nothing from `app.ocr` or `app.extraction` — asserted by a test.

---

## 6. Open questions

1. **Threshold values** for bold, proportion, and contrast are engineering judgement until
   the corpus exists. They are named constants; tuning changes one place and the accuracy
   suite catches the fallout. (PRD open question 2.)
2. **Bold elsewhere in the warning.** §16.22 requires the `GOVERNMENT WARNING` prefix to be
   bold; whether bold in the remainder is *prohibited* is unconfirmed. We verify the
   requirement, not the converse. (PRD open question 4.)
3. **Country of origin.** Required for imports (§5.69); the application form has no
   "is this an import" flag. Provisionally: checked only when the application declares a
   country. Revisit if the corpus shows this is wrong.
