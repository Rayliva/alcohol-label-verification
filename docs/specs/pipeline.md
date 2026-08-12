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
  ├─ decode            upright RGB; resample if over MAX_WORKING_EDGE
  ├─ quality gate      readable? if not, stop with a specific reason   (FR-15)
  ├─ OCR               text + bounding boxes
  ├─ extraction        OCR text -> structured fields (LLM, text only)
  ├─ measurement       bounding boxes + pixels -> LayoutMetrics
  ├─ rule engine       fields + metrics -> FieldResult[]               (pure)
  └─ evidence crops    bounding boxes -> one PNG per field             (FR-13)
```

Everything after decode sees the same pixels, OCR included. That is the point
of doing it once and at the front: a quality gate measuring one image while OCR
reads another is a tool that can report a blur nothing else can see.

The vision model is **not** on this path. It is the escalation route for images
the quality gate flags as marginal, and it costs seconds we do not have on the
hot path (tech-spec §Architecture).

---

## 2. Behaviour

### 2.0 Decode and resample — `run.py::_decode`

An upload is opened, uprighted from its EXIF orientation tag, and converted to
RGB. If its long edge is above `MAX_WORKING_EDGE` (2,000 px) it is resampled to
that edge once, and the resampled bytes are what the OCR engine receives.

**Why 2,000.** It is the top of the range every threshold in this pipeline was
calibrated against, not a number above it: the largest curated label is 2,000 px
on its long edge and the largest sample label 1,932. So nothing any threshold
was measured on is resampled, and anything that is resampled lands inside the
range the thresholds have evidence for.

**Why at all.** Measured against the deployed instance on 2026-08-11, the same
label at 1372x1852 and at 4116x5556 came back in 2.7 s and 9.3 s. The quality
gate went from 302 ms to 2,923 ms and measurement from 299 ms to 2,602 ms, both
at a resolution neither can use, and both reached the verdict they reach now.
Afterwards the 22-megapixel photograph has a server-side p50 of 3,313 ms and a
p95 of 4,231 ms (n=10).

Oversized JPEGs are handed to libjpeg with a draft size first, so they are
decoded at a half, quarter or eighth of stored size rather than decoded whole
and then shrunk: 88 ms against 256 ms locally on that photograph.

**Acceptance criteria**

- Given an image at or below 2,000 px on its long edge, when it is decoded,
  then the pixels and the bytes passed to OCR are unchanged.
- Given a 4116x5556 photograph, when it is decoded, then the working image is
  1482x2000 and OCR receives bytes of that size.
- Given one photograph measured at its native size and after resampling, when
  the cropped-label check runs on each, then both give the same answer.

### 2.1 The quality gate — `quality.py`

Runs before OCR, on the decoded image as §2.0 leaves it, and again after OCR
on what came back.
Each failure names its cause and what to do about it. **No generic failure ever
reaches a user** (`.claude/rules/error-handling.md`).

| Code | Detected by | Message names |
|---|---|---|
| `image_too_small` | Long edge below 700 px | The actual size and a working size |
| `image_too_blurry` | Edge energy below threshold, measured after the tonal range is stretched so exposure does not masquerade as focus | That a sharper photo at the same angle works |
| `glare_obscures_text` | A large near-white region covering part of the label | Which part of the label is covered |
| `image_too_dark` | Mean luminance below threshold | That the photo is underexposed |
| `no_text_found` | OCR returned nothing usable | That no text could be read at all |
| `text_unreadable` | OCR confidence far below normal | That the text present could not be read reliably |

**Focus is measured independently of exposure.** Sharpness was originally the
standard deviation of `image - blur(image)` on the raw greyscale. That measure
scales with the image's tonal range, so dimming a photograph lowered it without
any loss of focus, and a sharp label was reported to the agent as *blurry*. An
agent acting on that re-shoots for focus and hits the same wall, which is the
failure mode FR-15 exists to prevent.

Focus is now measured on a median-filtered copy, scaled by the image's white
point — the luminance the brightest 1% of pixels reach. Two deliberate choices:

- **White point, not full range.** Underexposure scales the whole signal, and
  the white point scales with it, so dividing by it removes the exposure term.
  Normalising by the min-to-max range instead (what `autocontrast` does) looks
  equivalent and is not: that range collapses on any *low contrast* frame
  whatever its exposure, so the gain grows without bound and sensor grain is
  counted as detail. Measured, that scored a label blurred past reading at
  9.27 — well clear of any sane threshold — and would have shipped a new
  wrong-cause failure pointing the other way.
- **Median filter first.** It removes isolated noisy pixels and leaves real
  edges, so the grain every phone JPEG carries cannot be read as sharpness.

Calibration, reproducible from this repo — corpus figures from `corpus/out`
(`python corpus/generate.py --all`), synthetic figures from the fixtures in
`api/tests/unit/test_quality.py`:

| Image | Focus | Must be |
|---|---|---|
| `t4-noise` | 24.45 | read |
| `t4-near-black` | 15.88 | *refused, as too dark* — see ordering below |
| `t4-low-light` | 15.62 | read |
| `t1-clean-classic-1` | 15.57 | read |
| `t4-jpeg-artefacts`, `t4-downscale`, `t4-skew`, `t4-glare-*` | 12.11 – 13.70 | read |
| synthetic sharp, and the same label dimmed to 0.14 or grained | 8.05 – 8.36 | read |
| `t4-blur-light` | 5.19 | read |
| synthetic: blurred r11, dim **and** grained | 1.90 | refused |
| synthetic: blurred r11 + grain | 0.57 | refused |
| `t4-blur-heavy` | 0.07 | refused |

`MIN_FOCUS = 2.9` is the geometric midpoint of 1.90 — the worst frame that must
be refused — and 4.31, the worst that must still be read. That 4.31 comes from a
300-label set of externally authored spirits labels carrying angle, glare, low
light, blur and curvature. **That set is not committed to this repo**, so the
figure cannot be re-derived here; it is named because it is one endpoint of the
calculation, not offered as evidence. On committed data alone the worst
must-read frame is `t4-blur-light` at 5.19, giving √(1.90 × 5.19) = 3.14 — so
2.9 holds either way, and every other figure above is reproducible here.

**Known limitation: a frame that is blurred, underexposed *and* noisy can still
be misreported.** Grain surviving the median filter contributes high-frequency
energy that is indistinguishable from the attenuated real edges of a very dim
sharp label. Measured on the raw edge statistic, before any normalisation:

| Image | Raw edge energy |
|---|---|
| Sharp label dimmed to 0.14 — must be read | 1.082 |
| Blurred r11 with grain — must be refused | 1.079 |

They are the same number. No threshold on this statistic separates them, and a
conjunction of the normalised and raw measures cannot either, so the boundary is
a property of the measure rather than of the cutoff. Composite degradations of
this kind land on whichever side the threshold happens to fall.

The consequence is bounded: the OCR-side checks (`no_text_found`,
`text_unreadable`, below) are the backstop, so the failure mode is a *wrong
cause* on an image that is refused anyway, not a false PASS. That has not been
measured against a live OCR provider. Separating these properly needs a measure
that distinguishes coherent edges from isolated grain — a spectral or
edge-continuity statistic rather than a scalar — which is more than this gate
warrants today.

Exposure keeps its own separate test. `image_too_dark` requires *both* low
luminance and low contrast and is checked **before** focus, which is
load-bearing rather than cosmetic: `t4-near-black` reads 15.88 on the focus
measure — normalisation does its job even on a near-black frame — so without
the dark check running first it would be judged perfectly sharp and passed
through. The raw edge-energy measure is retained for noise detection, where
absolute magnitude is the point.

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

  Resampling (§2.0) is the one exception, and it is stated rather than hidden.
  It cannot change what the label *says*, but it does change two measurements
  that are counted in pixels: focus, and the border-ink fraction. Both were
  brought into line rather than left implicit. The border band is a fraction of
  the long edge, so the cropped-label check asks the same question at every
  resolution. Focus is deliberately measured on the resampled image, because
  the question worth answering is whether the text OCR is about to read is
  sharp, not whether pixels nobody reads were.
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
