# Spec — Verification pipeline

**Status:** approved for build, Phase 2
**Date:** 2026-08-09
**Traces to:** `docs/PRD.md` FR-2, FR-3, FR-4, FR-13, P1-11, NFR-1 · `docs/tech-spec.md` → Architecture
**Implements:** `api/app/pipeline/`

---

## 1. What this is

The pipeline turns an uploaded image plus a declared application into a
`LabelReport`. It is the only place that touches pixels; the rule engine below it
sees data.

```
image bytes
  ├─ quality gate      readable? if not, stop with a specific reason   (FR-15)
  ├─ OCR               text + bounding boxes
  ├─ extraction        OCR text -> structured fields (LLM, text only)
  ├─ measurement       bounding boxes + pixels -> LayoutMetrics
  ├─ rule engine       fields + metrics -> FieldResult[]               (pure)
  └─ evidence crops    bounding boxes -> one PNG per field             (FR-13)
```

The vision model is **not** on this path. It is the escalation route for images
the quality gate flags as marginal, and it costs seconds we do not have on the
hot path (tech-spec §Architecture).

---

## 2. Behaviour

### 2.1 The quality gate — `quality.py`

Runs before OCR, on the decoded image, and again after OCR on what came back.
Each failure names its cause and what to do about it. **No generic failure ever
reaches a user** (`.claude/rules/error-handling.md`).

| Code | Detected by | Message names |
|---|---|---|
| `image_too_small` | Long edge below 700 px | The actual size and a working size |
| `image_too_blurry` | Edge-energy below threshold | That a sharper photo at the same angle works |
| `glare_obscures_text` | A large near-white region covering part of the label | Which part of the label is covered |
| `image_too_dark` | Mean luminance below threshold | That the photo is underexposed |
| `no_text_found` | OCR returned nothing usable | That no text could be read at all |
| `text_unreadable` | OCR confidence far below normal | That the text present could not be read reliably |

These produce `UnreadableImageError`, which the API renders as
`overall: "unreadable"` with an `error` object. **Unreadable is not FAIL.** A
badly photographed compliant label is not a violation, and conflating the two
corrupts every accuracy number we publish (PRD FR-3).

### 2.2 Measurement — `measure.py`

Produces the `LayoutMetrics` the geometric warning checks need. Every value is
optional; when a measurement cannot be taken the field is `None` and the rule
engine returns NEEDS_REVIEW rather than PASS.

| Metric | How |
|---|---|
| `median_text_height` | Median OCR block height — one oversized brand name must not skew it |
| `warning_text_height` | Height of the block carrying `GOVERNMENT WARNING` |
| `warning_prefix_stroke_ratio` | Ink density of the prefix region ÷ ink density of the rest of the warning, at equal text height. A **proxy** for stroke weight |
| `warning_contrast_ratio` | WCAG contrast between the 5th and 95th percentile luminance inside the warning region |
| `field_sides` | Which panel each field's block sits on. A container photographed as front + back reads as a wide image; a single panel puts everything on `front` |

Every one of these is a proxy for something the regulation states absolutely.
They are documented as proxies in the README, not presented as measurements of
the regulatory quantity.

### 2.3 Evidence crops — `crops.py`

For each field, the region of the image its value came from, as PNG bytes.
Located by matching the detected value against OCR block text after
normalisation. `None` when the field was not found on the label — a field that
is absent has no region to crop (ui-spec resolution 3).

Crops carry padding so the agent sees context, and are capped in size so a batch
of 200 does not carry 200 full-resolution images.

### 2.4 Orchestration — `run.py`

`verify(image_bytes, application, *, ocr, extract) -> VerificationResult`

`ocr` and `extract` are injected. Mocking happens at those two boundaries and
nowhere else (`.claude/rules/test-driven-development.md`).

The result carries per-stage timings — preprocess, OCR, extraction, rules,
crops — because NFR-1 requires published numbers and we cannot publish what we
do not measure.

---

## 3. Boundaries

- **No persistence.** Images and crops live in memory for the length of one
  request (PRD C-2).
- **No preprocessing that changes the verdict.** Deskew and contrast help OCR;
  they never rewrite what the label says.
- **No absolute type-size measurement.** See `rule-engine.md` §4.
- **No batch orchestration here.** Batch is a layer above, calling `verify` once
  per label.

---

## 4. Acceptance criteria

1. A compliant rendered label returns `overall == PASS` with a `FieldResult` for
   every configured field.
2. A 400×300 image raises `UnreadableImageError` with code `image_too_small`,
   and the message states the actual size.
3. A heavily blurred label raises `image_too_blurry`, not a generic failure.
4. An unreadable image never produces field verdicts.
5. Every field found on the label has a non-null crop; a field absent from the
   label has a null crop.
6. `LayoutMetrics.median_text_height` is populated for any label with text.
7. A label whose warning prefix is not bold produces a stroke ratio below the
   bold threshold.
8. Per-stage timings are present and sum to no more than the total.
9. The pipeline calls the extraction model exactly once per label.
10. `verify` never raises for a readable label — a rule that cannot run returns
    NEEDS_REVIEW.

---

## 5. Open questions

1. **Blur and glare thresholds** are tuned against tier 4 of the corpus, which
   is half degraded-but-readable and half unreadable by construction. Published
   with the accuracy numbers.
2. **Vision escalation** (PRD FR-11) ships if the corpus shows OCR failing on
   labels a human can read. Decided from measurement, not in advance.
