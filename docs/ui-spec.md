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

- Show the stage in plain words: *Sending the image → Reading the label and
  checking every field*
- Show elapsed seconds
- Keep the uploaded image visible
- **No indeterminate spinner alone**

**Only claim what is measured.** This screen originally ran three named stages
off fixed offsets taken from an old benchmark, so "checking each field against
the application" was the stage on screen whenever the wait ran long, whether or
not anything was being checked. It made a slow model call look like a slow rule
engine. The browser can honestly measure exactly two things, how much of the
image has gone up and how long it has been, so those are the two the screen
reports. The second stage is paced by the published median and held short of
full until the answer arrives.

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

Plus the verdict badge, the reading confidence as a number and a word, and a one-sentence plain-language reason. The confidence bar that once sat beside them was removed: it repeated the number without adding a fact, and the vertical space cost more than it was worth on a screen with six of these.

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

**Only the rows the tool flagged carry a decision.** A field verdicted `pass` has nothing to disagree with, and asking about it made an agent confirm five verdicts that were never in doubt before reaching the one that was. `needs_review` and `fail` rows, and the government warning block, carry the question the controls are actually asking, `The tool flagged this as X. Do you agree?`, with `No, accept this field` and `Yes, it is a problem`. The note is enabled once a decision is picked, so it is never typed into a void.

Decided rows are visibly marked as agent-decided, showing both the original verdict and the decision, never silently replaced. A rejected row must not render a `pass` badge, which it did until 2026-08-11.

**Say where the decision goes.** These decisions travel with the CSV export and nowhere else, because nothing about an application is stored (PRD C-2). The control used to say a note "goes on the record", which was false in a product that has no record.

**Screen actions:** `Export results` (CSV) and `Back to the queue`. When the results are embedded in the review screen, that screen owns the page's one dominant action and the back button is suppressed rather than duplicated.

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

### 1. One shared credential, and an optional reviewer name

**Superseded on 2026-08-11.** This section originally read "no login": the brief never asks for auth, and real auth would mean storing credentials, which contradicts the no-persistence constraint.

What changed is that the prototype is deployed at a public URL. A review queue of applications served to anyone who finds it is worse than the small amount of auth needed to close it, so there is **one shared agent credential**, read from the environment, carried in a signed HttpOnly cookie. The app refuses to start without it. That is the whole of it: no accounts, no password hash at rest, no reset, no roles, nothing stored.

The optional **"Your name or initials"** field stays, and is still what populates `Reviewed by R. Delgado`. Blank is valid and common; when blank, omit the attribution clause entirely rather than showing a dangling "Reviewed by".

Production auth (agency SSO / PIV, role separation, audit logging) is documented in the README as a production consideration, not built.

### 2. `unreadable` is a fourth overall state

Screen 5 correctly counts four buckets. The data model now matches: `overall` accepts `unreadable`, carrying an `error` object.

**Unreadable is not the same as fail.** "We could not read this" must never be reported as "this label is non-compliant" — the label may be perfectly compliant and merely badly photographed. Keep them in separate buckets everywhere.

**Screen 6 needs a fourth filter chip** — `Could not be read (N)` — to match Screen 5's tiles. Currently missing.

### 3. `crop_url` is nullable

A field absent from the label has no region to crop. `crop_url` may be `null`, and the panel keeps its dimensions with the copy:

> **Not found anywhere on the label**

Same panel size and border as a real crop, so row height does not jump. There is no caption line under the crop: it printed a filename that told an agent nothing the panel had not already told them, in the smallest type in the product.

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

---

## Where the implementation diverges from the design handoff (2026-08-11)

`docs/design/design_handoff_label_check/README.md` is a received artifact and is
not edited, in the same way `requirements.md` is not. It asks to be recreated
pixel-accurately. Four things are deliberately not, and this is the record of
why.

| Handoff | Shipped | Why |
|---|---|---|
| h1 34px, h2 26px, h3 23px | 29 / 22 / 20 | Body stays at 19px and nothing goes below 16px, so every accessibility constraint still holds. The headings were consuming the screen an agent needed for the results |
| Page padding `32px 40px 96px`, card padding `26–28px`, card gap 18px | `22px 32px 56px`, `18px 20px`, gap 14px | Same reason. An agent could see roughly one field result at a time |
| Crop panel 110px / 150px | 92px / 170px | The warning crop is the one that repays being larger; the field crops do not |
| One column of field results | Two columns above 1500px | The single largest gain in how much of a result is visible at once, and it costs nothing below that width |

Everything else in the handoff, every colour, every contrast ratio, the
three-state encoding, the evidence crop being inline and never behind a
control, is implemented as specified.

The handoff also specifies an `Undo my decision` control and a confidence bar.
Neither shipped: pressing the chosen decision again clears it, which is what
`aria-pressed` already communicates, and the bar repeated the number beside it.

---

## Session 6 decisions (2026-08-11, later that day)

All decided by the product owner in review of the running app.

1. **The product is called Alcohol Label Verification**, not Label Check.
2. **No beverage type selector.** Spirits is the scope; a selector offering two
   disabled choices was two explanations nobody needed. The API keeps its
   config-driven engine and `/api/beverage-types`; the UI sends `spirits`.
3. **No permanent status line above the primary action.** The button is always
   enabled; pressing it with something missing raises an alert naming every
   missing item. Rule 9 is satisfied by never disabling the control.
4. **Per-card "Why?" disclosure.** The reason, reading confidence, rule
   citation and the agent's decision controls sit behind a disclosure on each
   field card. This is a deliberate deviation from rule 5, accepted because
   six cards of rationale crowded out the results: the verdict, both values
   and the evidence crop stay in the open.
5. **A passing field can be flagged.** Behind its disclosure, a pass card
   offers one action, "Flag as a problem", for the case where the agent spots
   what the tool missed. Accepting a pass remains meaningless and is not
   offered.
6. **Images enlarge on click.** Evidence crops and the submitted artwork open
   in a dialog with a zoom toggle; Esc, the backdrop or the close button
   dismisses it. The inline view is never gated behind the click.
7. **The summary drops "spirits" and "read in N seconds".** Elapsed time is
   demonstrated live on the processing screen; restating it afterwards earned
   its space nothing.
8. **The masthead shows the TTB seal cropped square.** The asset's wordmark
   half rendered illegibly at masthead size and pushed the product name a
   hand's width from the mark.
9. **Bottler address help corrected.** 27 CFR 5.66 requires city and State,
   not a street address (verified against Cornell LII, 2026-08-11, recorded in
   .claude/rules/verify-regulations.md).

### Session 6 amendments (2026-08-11, still later)

- **Item 5 is reversed.** A passing field carries no controls at all. The
  recorded way to disagree with a clean label is the application-level Reject
  on the review screen, which exists whatever the verdicts were. The per-field
  "Flag as a problem" lived for about an hour.
- **The verdict badge and its "Why?" disclosure move below the evidence**, so
  what the disclosure expands is visibly attached to the verdict it explains.
- **The sign-in page is the card alone.** No masthead, no product description,
  no mention that the account is shared (which helped exactly the person the
  gate keeps out). Seal enlarged and centred, title centred, button centred.
- **Government restyle.** Flat grey surfaces, square corners, navy masthead
  with a gold rule (both colours from the seal), USWDS link blue, buttons
  outlined or filled navy. Public Sans stays: it is the USWDS face. Every
  contrast ratio re-checked against the accessibility rules; the token file
  carries the measured values. This supersedes the design handoff's warm
  palette, which the owner judged too modern for the audience.
