# UI Spec — AI-Powered Alcohol Label Verification

**Purpose:** the brief for designing this application's interface. Hand this document to a design pass; it defines every screen, state, and piece of data. Phase 2 of the build implements the result.

**Status:** ready for design. Design happens during Phase 1, in parallel with the headless rule engine.

---

## Read this first

This UI is **scored on task completion by a non-technical user, not on visual sophistication.** The brief's stated bar:

> *"We need something my mother could figure out — she's 73 and just learned to video call her grandkids last year, if that gives you a benchmark. Half our team is over 50. Clean, obvious, no hunting for buttons."*

The users are federal compliance agents reviewing ~3,200 label applications a year each. One has 28 years of experience and still prints his emails; he is skeptical of new tools and will abandon anything that slows him down. Another is fresh out of college and fast. **The design must work for the first person without insulting the second.**

### Hard constraints — non-negotiable

Every one is checkable on a rendered screen. A design that violates any of these will be rejected regardless of how it looks.

| # | Requirement | Threshold |
|---|---|---|
| 1 | Interactive target size | ≥ 44 × 44 px |
| 2 | Body text | ≥ 16px. Nothing below 14px anywhere, including captions and table cells |
| 3 | Contrast | WCAG AA — 4.5:1 body text, 3:1 large text and UI borders |
| 4 | Primary action | Exactly one visually dominant action per screen |
| 5 | No hidden state | No hover-only affordances. No meaning carried by color alone. No important content behind disclosure |
| 6 | Keyboard | Every action reachable by Tab, activated by Enter/Space, with a visible focus ring |
| 7 | Accessible names | Every control has a text label. **No icon-only buttons** |
| 8 | Progress | Determinate where the total is known — "47 of 200", never an indeterminate spinner |
| 9 | Disabled controls | Never disabled without adjacent text explaining why |

### Anti-goals

Design tools optimize for looking good. This one is optimized for something else. Specifically avoid:

- Small elegant type — 14px body is a failure here, not a style
- Subtle low-contrast greys for secondary text
- Icon-only toolbars
- Hover-revealed actions or hover-only tooltips carrying real information
- Dense data tables that fit more rows by shrinking everything
- Color-only status indicators (red dot / green dot)
- Multi-step wizards where one screen would do
- Animated transitions that delay information

**Plain and obvious beats clever.** If a choice trades clarity for elegance, take clarity.

---

## The product in one line

An agent uploads a label image plus the data declared in its application. Within ~5 seconds the tool shows, field by field, whether the label matches — with the cropped piece of the image proving each verdict. The agent confirms or overrides. **The tool advises; the agent decides.**

---

## Core concept: the three-state verdict

Every field resolves to one of three states. This is the single most important element in the UI and appears on nearly every screen.

| State | Meaning | Agent action |
|---|---|---|
| **PASS** | Label matches the application | None |
| **NEEDS REVIEW** | Close but not certain — formatting difference, low OCR confidence, or a judgment call | Look and decide |
| **FAIL** | Genuine mismatch or missing required element | Reject or investigate |

**Binary pass/fail is explicitly wrong for this product.** A senior agent's example: the label reads `STONE'S THROW`, the application says `Stone's Throw`. Technically different, obviously the same thing. A tool that calls that a failure gets ignored.

Each state must be distinguishable **three ways at once** — color, icon, and text — so it survives colorblindness and printing:

```
✓  Pass            green
⚠  Needs review    amber
✕  Fail            red
```

---

## Screen 1 — Single label: input

The default landing screen. One job: collect an image and the declared field values.

**Layout:** two columns on desktop (image left, form right), stacked on narrow screens.

**Image upload**
- Large drop zone with a visible "Choose file" button — drag-and-drop alone is not discoverable
- Accepts JPG, PNG, PDF
- After selection: thumbnail preview, filename, and a clear "Remove" control
- Beverage type selector: **Spirits / Wine / Malt beverage** — three visible options, not a dropdown

**Declared fields** (this is the COLA application data)

| Field | Input | Required |
|---|---|---|
| Brand name | text | yes |
| Class / type designation | text | yes |
| Alcohol content | text — accepts `45% Alc./Vol. (90 Proof)` | conditional by beverage type |
| Net contents | text — accepts `750 mL` | yes |
| Bottler / producer name and address | textarea | yes |
| Country of origin | text | imports only |

Labels are plain language. Help text sits **under** the field, always visible — never in a tooltip.

**Primary action:** one large button, `Check this label`. Disabled until an image and the required fields are present, with adjacent text naming what's still missing.

**Secondary:** a quiet link to batch mode.

---

## Screen 2 — Single label: processing

Visible for ~2–5 seconds. Its job is to make the wait legible.

- Show the stage in plain words: *Reading the label… → Checking each field…*
- Show elapsed seconds
- Keep the uploaded image visible
- **No indeterminate spinner alone**

If it exceeds 10 seconds, say so and offer to cancel. Silence reads as broken.

---

## Screen 3 — Single label: results

The most important screen in the product.

**Summary bar (top)**

Overall outcome plus counts: `2 issues found — 4 pass, 1 needs review, 1 fail`. Uses the same three-way encoding.

**Field-by-field results**

One row or card per field. **Each shows four things side by side, always visible:**

| Element | Content |
|---|---|
| Field name | "Brand name" |
| Declared | What the application says |
| Detected | What we read from the label |
| Evidence | The cropped region of the image the value came from |

Plus the verdict badge, a confidence indicator, and a one-sentence plain-language reason.

**The evidence crop is the heart of this screen.** It lets an agent distinguish "the label is genuinely wrong" from "we misread it" in about a second, and it is the entire answer to the experienced agent's skepticism. **Never put it behind a click or a hover.**

Example row:

```
Alcohol content                                    ⚠ Needs review

Declared:  45% Alc./Vol. (90 Proof)
Detected:  45% ALC/VOL (90 PROOF)          [ crop of that region ]

Formatting differs; values match. Confidence 0.91.
```

**Government warning — give it more room**

It is the only exact-match check and has the most failure modes. Show the full detected text with any difference from the statutory text highlighted inline, plus sub-checks as their own labeled rows:

- Text matches exactly
- `GOVERNMENT WARNING` in capital letters
- `GOVERNMENT WARNING` in bold
- Size relative to surrounding text
- Contrasting background

**Agent override**

Every field row carries `Accept` and `Reject` controls plus an optional note. Overridden rows are visibly marked as agent-decided, showing both the original verdict and the override — never silently replaced.

**Screen actions:** `Export results` (CSV/JSON) and `Check another label`.

---

## Screen 4 — Batch: upload

For peak season, when large importers submit 200–300 applications at once.

- Multi-file image upload with a visible count: "247 images selected"
- Manifest upload (CSV or JSON) pairing each image with its application record
- **A downloadable template CSV** — do not make anyone guess the column names
- After both are present, show a pre-flight summary before processing starts:

```
247 images · 247 manifest rows · 247 matched

Ready to check.
```

Mismatches are surfaced *here*, not after a four-minute run: unmatched images, manifest rows with no image, malformed rows. Each named specifically with its filename or row number.

---

## Screen 5 — Batch: progress

Runs for several minutes. Must remain informative throughout.

- Determinate bar: `47 of 200 checked`
- Elapsed and estimated remaining
- Running counts by state, updating live
- **Results stream in as they complete** — an agent can start reviewing failures before the run finishes
- A visible `Stop` control

---

## Screen 6 — Batch: results table

**Sorted problems-first by default.** An agent should never hunt for the failures — this is a stated requirement, not a preference.

| Column | Notes |
|---|---|
| Status | Three-way encoded, sortable |
| Application ID | From the manifest |
| Brand name | |
| Issues | "2 issues" or "—" |
| Thumbnail | Small label preview |

Row height generous. Clicking any row opens the full Screen 3 detail for that label, with prev/next navigation so an agent can work the queue without returning to the table.

Above the table: filter chips (`All` / `Failures` / `Needs review` / `Passed`) with counts on each.

`Export all results` as the screen's primary action.

---

## Screen 7 — Errors and unreadable labels

**Never show a generic failure.** An agent who reads "processing failed" learns nothing, rejects the application, and concludes the tool wastes their time.

| Situation | Message |
|---|---|
| Glare | "Glare covers the lower third of the label. Re-photograph without direct light on the bottle." |
| Blur | "Image is too blurry to read the text. A sharper photo at the same angle should work." |
| Resolution | "Image is 400×300. Text this small can't be read reliably — 1000px or wider works best." |
| Cropped | "The bottom of the label appears cut off. The government warning may be outside the frame." |
| Service down | "Can't reach the label reading service right now. Your entry has been kept — try again in a moment." |

Every error states **what happened** and **what to do next**. Where partial results exist, show them alongside the error rather than discarding the run.

---

## Data shape

What the API returns per label, so the design knows exactly what it has to work with:

```jsonc
{
  "label_id": "app-10482",            // optional; may be null (see Application ID below)
  "beverage_type": "spirits",
  "overall": "needs_review",          // pass | needs_review | fail | unreadable
  "processing_ms": 2310,
  "reviewer": "R. Delgado",           // optional, session-only; may be null
  "error": null,                      // populated only when overall == "unreadable"
  "fields": [
    {
      "field": "alcohol_content",
      "display_name": "Alcohol content",
      "declared": "45% Alc./Vol. (90 Proof)",
      "detected": "45% ALC/VOL (90 PROOF)",
      "verdict": "needs_review",
      "confidence": 0.91,
      "reason": "Formatting differs; values match.",
      "crop_url": "/crops/app-10482/alcohol_content.png",  // nullable — see below
      "override": null                 // or { decision, note, at }
    }
  ],
  "warning_checks": [
    { "check": "text_exact",  "verdict": "pass", "reason": "Matches 27 CFR 16.21 exactly." },
    { "check": "caps",        "verdict": "pass", "reason": "GOVERNMENT WARNING is in capitals." },
    { "check": "bold",        "verdict": "needs_review", "reason": "Stroke weight only slightly above body text." },
    { "check": "proportion",  "verdict": "pass", "reason": "Warning text is 92% of body text height." },
    { "check": "contrast",    "verdict": "pass", "reason": "Dark text on light background." },
    { "check": "field_of_vision", "verdict": "pass", "reason": "Brand, class and alcohol content share one side." }
  ]
}
```

When `overall == "unreadable"`:

```jsonc
"error": {
  "code": "glare_obscures_text",
  "message": "A bright reflection covers the lower third of the label...",
  "what_to_do": "Re-photograph the bottle without direct light on it...",
  "partial_fields_shown": true
}
```

---

## Resolutions from design review (2026-08-09)

Six items reconciled between the design handoff and the requirements. All are small additions; none require redesign.

### 1. No login — optional reviewer name instead

The product has **no authentication, no accounts, no user records** (PRD OS-1). The brief never asks for auth, and real auth would require storing credentials — contradicting the no-persistence constraint.

So `Reviewed by R. Delgado` and `Decided by R. Delgado` are **not** populated from a login. Add a single optional **"Your name or initials"** field, entered once and held in session state. Blank is valid and common — when blank, omit the attribution clause entirely rather than showing "Reviewed by —".

Production auth (agency SSO / PIV, role separation, audit logging) is documented in the README as a production consideration, not built.

### 2. `unreadable` is a fourth overall state

Screen 5 correctly counts four buckets. The data model now matches: `overall` accepts `unreadable`, carrying an `error` object.

**Unreadable is not the same as fail.** "We could not read this" must never be reported as "this label is non-compliant" — the label may be perfectly compliant and merely badly photographed. Keep them in separate buckets everywhere.

**Screen 6 needs a fourth filter chip** — `Could not be read (N)` — to match Screen 5's tiles. Currently missing.

### 3. `crop_url` is nullable

A field absent from the label has no region to crop. `crop_url` may be `null`, and the panel keeps its dimensions with the copy:

> **Not found anywhere on the label**

Same panel size, border, and caption slot as a real crop, so row height doesn't jump. The caption line reads `no crop — field not present`.

### 4. Alcohol content: required for spirits only

The handoff marks it required for spirits **and** wine. Per 27 CFR 4.36, wine at ≤14% ABV may legally omit the percentage when the label states "table wine" or "light wine" — so requiring it would block a valid application.

| Beverage type | Alcohol content field |
|---|---|
| Spirits | Required |
| Wine | Optional — help text: "Not required for table wine at 14% or less." |
| Malt beverage | Optional — help text: "Only required when alcohol comes from added flavors." |

### 5. Application ID — optional, and an identifier for nothing

Add an optional **"Application ID"** text input (mono) to Screen 1, above Brand name. Help text: *"The COLA application number, if you have it. Used to label your results."*

This is TTB's existing identifier, transcribed by the agent — **we never generate it.** There is no database, so it is a key to nothing: it is an opaque display string echoed into results and exports, never used to look anything up and never trusted as input. When blank, the summary metadata line omits it.

### 6. Same field of vision — sixth sub-check

27 CFR 5.63 requires brand name, class/type, and alcohol content to appear on the same side of the container for spirits. Add it as a **sixth row in the warning-block sub-check list** (it uses the same component), labeled *"Brand, class and alcohol content on one side"*.

Spirits only — hide the row for wine and malt. This is a P2 feature; reserve the row now so it isn't bolted on later.

### 7–9. Minor

- **Self-host the fonts.** Public Sans and IBM Plex Mono ship with the app rather than loading from `fonts.googleapis.com`. Removes a runtime dependency on an external domain, which matters given the firewall constraint (C-3) and keeps the on-prem story honest.
- **Batch time estimate is computed**, from measured throughput — never a hardcoded constant. See `.claude/rules/measure-dont-claim.md`.
- **Wine and Malt beverage buttons ship disabled** for Phase 1 (spirits only), with adjacent text: *"Wine and malt beverage checking is coming next."* Per accessibility constraint 9, a disabled control always explains itself. Keep the buttons visible rather than hiding them — they document the intended scope.

---

## Deliverables from the design pass

1. **Screens 1, 3, 5, and 6** — the four that carry the product. Desktop first (agents work at desks); Screens 2, 4, 7 can be described rather than fully composed.
2. **The field result row** as a reusable component, in all three verdict states plus the overridden state.
3. **A color and type scale** with contrast ratios stated, so compliance with constraint 3 is verifiable rather than asserted.
4. **The empty, loading, and error state** for each screen.

**Self-check before handing back:** walk the nine hard constraints against every screen. A design that fails one of them costs more to rework than it saved.
