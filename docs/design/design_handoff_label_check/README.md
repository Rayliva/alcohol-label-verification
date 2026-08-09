# Handoff: Label Check — AI-Powered Alcohol Label Verification UI

## Overview

Label Check is a desktop tool for federal compliance agents reviewing COLA label applications. An agent uploads a label image plus the values declared in the application; within ~5 seconds the tool reports, field by field, whether the label matches — showing the cropped region of the image that each verdict came from. The agent confirms or overrides every field. **The tool advises; the agent decides.**

Users are ~3,200 applications/year per agent, ages ranging from fresh graduate to 28-year veteran. The design is scored on **task completion by a non-technical user**, not visual sophistication. Every decision below follows from that.

## About the design files

`Label Check.dc.html` in this bundle is a **design reference created in HTML** — a prototype showing intended look and behavior, not production code to copy. The task is to **recreate these screens in the target codebase's existing environment** (React, Vue, whatever the Phase 2 stack is) using its established component patterns, routing, and data layer. If no environment exists yet, pick the framework appropriate to the project and implement there.

Open the file directly in a browser. The black strip at the top is a **prototype-only** screen switcher — it is not part of the product and must not be built.

## Fidelity

**High fidelity.** Colors, typography, spacing, and interaction behavior are final and specified exactly below. Recreate pixel-accurately. Two things are placeholders:

- **Evidence crops** render as a beige panel containing the detected text. In production these are real cropped `<img>` regions from `crop_url`. Keep the panel dimensions, border, and caption; swap the contents for the image.
- **Label thumbnails** in the batch table are gray boxes. Same treatment.

---

## The nine hard constraints

These are acceptance criteria, not guidelines. A build that violates one gets rejected. Check each against every screen you implement.

| # | Requirement | How the design satisfies it — preserve this |
|---|---|---|
| 1 | Interactive targets ≥ 44 × 44 px | Every button has `min-height: 44px` minimum; most are 48–68px. Inputs are 52px tall. |
| 2 | Body text ≥ 16px, nothing below 14px | Body is 19px. Help text 17px. Smallest text anywhere is 15px (image filenames only). |
| 3 | WCAG AA — 4.5:1 body, 3:1 large text and UI borders | See the color table. Every value is measured, not asserted. |
| 4 | Exactly one visually dominant action per screen | Listed per screen below. Do not add a second filled-black button to any screen. |
| 5 | No hidden state | No hover-only affordances anywhere. No tooltips. No accordions. Help text sits permanently under its field. Evidence crops are always visible. |
| 6 | Keyboard | Everything is a real `<button>`, `<input>`, `<textarea>`, or `<a>`. Global `:focus-visible { outline: 3px solid #1A4C8B; outline-offset: 2px }`. Do not remove outlines. |
| 7 | Accessible names — no icon-only buttons | Every control carries visible text. The `✓ ⚠ ✕` glyphs always sit next to a word. |
| 8 | Determinate progress | "47 of 200 checked" with a filled bar. Never an indeterminate spinner. |
| 9 | Disabled controls explain themselves | The primary button on Screen 1 is disabled only with adjacent red text naming exactly what is missing. |

### Anti-goals — do not introduce during implementation

Small elegant type · low-contrast gray secondary text · icon-only toolbars · hover-revealed actions or tooltips · dense tables that shrink to fit more rows · color-only status dots · multi-step wizards where one screen does · animated transitions that delay information.

---

## Design tokens

### Color

| Role | Hex | Contrast | Meets |
|---|---|---|---|
| Page background | `#F2F0EC` | — | background only |
| Surface / card | `#FFFFFF` | — | — |
| Body text on white | `#1A1917` | 16.9 : 1 | AA + AAA |
| Secondary text on white | `#3A3833` | 11.1 : 1 | AA + AAA |
| Smallest gray used | `#4A4843` | 8.7 : 1 | AA + AAA |
| Border / rule (structural) | `#8C877C` | 3.2 : 1 | AA for UI borders |
| Divider (decorative only) | `#DDD9D0` | — | never carries meaning |
| Inset panel / crop background | `#EFEBE2` | — | — |
| Zebra row / subtle fill | `#F7F5F1`, `#FBFAF8` | — | — |
| Link | `#1A4C8B` (hover `#0F3363`) | 8.0 : 1 | AA + AAA |
| Focus ring | `#1A4C8B` | 3px solid, 2px offset | — |

**Verdict colors** — each verdict is a triple of `{ text, border, tint }`:

| Verdict | Text | Border | Tint background | Text-on-tint contrast |
|---|---|---|---|---|
| Pass | `#22463C` | `#2F5D50` | `#EAF0EC` | 9.4 : 1 |
| Needs review | `#5C4400` | `#7A5B00` | `#FBF3DE` | 7.6 : 1 |
| Fail | `#7A2020` | `#8C2A2A` | `#F7E9E7` | 8.1 : 1 |
| Agent override | `#2C266B` | `#3B348C` | `#EDEBFB` | 11.4 : 1 |

### Typography

Fonts: **Public Sans** (400/500/600/700) for everything; **IBM Plex Mono** (400/500) for declared/detected values, application IDs, and filenames — so `0/O` and `1/l` are distinguishable when an agent compares two strings.

| Role | Size / weight / leading |
|---|---|
| Screen title (h1) | 34px / 700 / 1.2 |
| Section heading (h2) | 26px / 700 / 1.2 |
| Card + field name (h3) | 23px / 700 / 1.2 |
| Body, form inputs | 19px / 400 / 1.5 |
| Values (mono) | 19px / 400 / 1.45 |
| Help text, secondary | 17px / 400 / 1.5 |
| Column micro-labels | 16px / 600 / uppercase / `letter-spacing: .06em` / color `#3A3833` |
| Filenames (mono) | 15px / 400 — smallest text in the product |
| Primary button | 24px / 700 (Screen 1), 20–22px elsewhere |
| Verdict badge | 18px / 700 / uppercase / `letter-spacing: .04em` |

### Spacing, radius, borders

- Page padding `32px 40px 96px`; max content width `1840px`; header padding `18px 40px`.
- Card padding `26–28px`. Gap between stacked cards `18px`. Gap between form fields `22px`.
- Border radius: `6px` cards and sections, `4px` buttons, inputs, badges, panels, `3px` image placeholders.
- Borders are **2px** throughout (not 1px — 1px at `#8C877C` is too faint at agency monitor distances). Verdict cards add a `10px` left rail in the verdict color. Structural border color is always `#8C877C`.
- No shadows anywhere. No gradients. No transitions or animations except the two progress bars filling.

---

## The three-state verdict — the core concept

Every field resolves to `pass` | `needs_review` | `fail`. Binary pass/fail is explicitly wrong: a label reading `STONE'S THROW` against an application saying `Stone's Throw` is a **pass**, not a failure. The prototype demonstrates exactly this case on the Brand name row.

Each state is encoded **three ways simultaneously** — color, glyph, and word — so it survives colorblindness and black-and-white printing:

```
✓  PASS            green   #22463C on #EAF0EC, 2px #2F5D50 border
⚠  NEEDS REVIEW    amber   #5C4400 on #FBF3DE, 2px #7A5B00 border
✕  FAIL            red     #7A2020 on #F7E9E7, 2px #8C2A2A border
```

**Badge component:** `inline-flex`, `gap: 8px`, `padding: 10px 16px` (small variant `9px 14px`), radius 4px, `font: 700 18px/1 Public Sans` uppercase `letter-spacing: .04em`, `white-space: nowrap`. The glyph is a `<span style="font-size: 20px">` inside the badge. Never render the glyph alone; never render the color alone.

---

## Screens

### Screen 1 — Single label: input (default landing)

**Primary action:** `Check this label` — full-width, 68px tall, 24px/700, black `#1A1917` fill. The only filled-black control on the screen.

**Layout:** two columns, `grid-template-columns: minmax(560px,1fr) minmax(640px,1.1fr)`, `gap: 32px`, `align-items: start`. Stacks on narrow viewports.

**Left column — image and beverage type**

- *Empty state:* `3px dashed #8C877C` drop zone, `#F7F5F1` fill, `40px 28px` padding, centered. Reads "Drag a label image here" (20px/600) / "or use the button below" (17px) / **Choose file** button (52px, 2px black border, white fill). Drag-and-drop alone is not discoverable — the button is required.
- *Filled state:* 150 × 200px preview thumbnail, filename (19px/600), dimensions and file size (16px), a green line confirming the resolution is readable, and a **Remove this file** button (44px).
- Accepts JPG, PNG, PDF.
- *Beverage type:* three visible buttons in a `repeat(3,1fr)` grid — **Spirits / Wine / Malt beverage**. Not a dropdown. Selected = black fill, white text, `◉`; unselected = white, `○`, `#8C877C` border. 60px tall. Set `aria-pressed`. Selection controls whether Alcohol content is required.

**Right column — declared fields**

Six fields, all with a visible `<label>` (19px/600), a required/conditional note in the label at 400 weight, and permanently visible help text underneath (17px, `#3A3833`). Never a tooltip.

| Field | Control | Required | Help text |
|---|---|---|---|
| Brand name | text | yes | "The name the product is sold under, e.g. Stone's Throw." |
| Class or type designation | text | yes | "What the product legally is, e.g. Straight Bourbon Whiskey." |
| Alcohol content | text, **mono** | required for spirits and wine | "Type it as written on the application, e.g. 45% Alc./Vol. (90 Proof)." |
| Net contents | text, **mono** | yes | "Volume in metric, e.g. 750 mL." |
| Bottler or producer name and address | textarea, 3 rows, min 96px | yes | "Full name and address, including street, city and state." |
| Country of origin | text | imports only | "Required only when the product is imported." |

**Validation (constraint 9):** the button is disabled until an image plus all required fields are present. Directly above it sits a line that, when incomplete, reads in `#7A2020` 18px/600: *"Still needed before this button works: a label image, Net contents."* — naming every missing item by its exact field label. When complete it turns `#22463C` 400 weight: *"Everything required is filled in."* Disabled button style: `#D8D4CB` fill, `#4A4843` text, `#8C877C` border, `cursor: not-allowed`.

**Secondary:** a quiet underlined text button, *"Have a lot of these? Check a batch of labels instead."*

---

### Screen 2 — Single label: processing (~2–5s)

**Layout:** single card, `grid-template-columns: 220px 1fr`, `gap: 40px`. The uploaded image stays visible on the left the entire time.

- Three named stages as an `<ol>`, each with a 34px circular marker: `·` pending → `…` active → `✓` done (green border `#2F5D50`, tint fill). Labels in plain language: "Uploading the image" → "Reading the text on the label" → "Checking each field against the application". Completed and active stages go 600 weight `#1A1917`; pending stays 400 `#4A4843`.
- Determinate bar underneath, 16px tall, max 520px, black fill.
- Elapsed time in mono, 19px: *"2.4 seconds so far."*
- **Over 10 seconds:** an amber panel appears — "This is taking longer than usual / The reading service is slow right now. Your entry is saved either way." — with a **Cancel and go back** button. Silence reads as broken.

No indeterminate spinner at any point.

---

### Screen 3 — Single label: results (the most important screen)

**Primary action:** `Check another label` — black fill, top right of the summary bar. `Export results (CSV)` sits beside it as a white secondary.

**Summary bar.** Full-width panel tinted to the overall verdict (here amber: `#FBF3DE` fill, `2px #7A5B00` border, `12px` left rail). Left: a 56px white square holding the verdict glyph at 30px, then `h1` "3 issues found on this label" (34px/700), then counts "4 fields pass · 2 need review · 1 fails" (20px), then a metadata line "Application app-10482 · Spirits · Read in 2.3 seconds · Reviewed by R. Delgado" (17px).

**Field rows — the reusable component.** One card per field, sorted **problems first** (fail → needs review → pass).

```
Card: white, 2px #8C877C border, 10px left rail in the verdict color, radius 6px, padding 26px 28px.

Row 1  Field name (23px/700)                             …                    [ VERDICT BADGE ]
Row 2  grid-template-columns: 1fr 1fr 340px; gap: 24px
       ┌ DECLARED IN APPLICATION ─┬ DETECTED ON LABEL ──┬ EVIDENCE FROM THE IMAGE ┐
       │ mono 19px                │ mono 19px           │ crop panel, 110px tall  │
       │                          │                     │ crop · alcohol_content.png │
Row 3  ── 2px #DDD9D0 divider ──
       Plain-language reason, one sentence, 19px
       "Reading confidence 0.91"  [====== bar 160×12 ======]  "(good)"
Row 4  ── divider ──
       [ Accept this field ] [ Reject this field ]   Note (optional) — goes on the record
                                                     [ text input, flex:1, min-width 320px ]
```

**The evidence crop is the heart of this screen.** It is what answers the veteran agent's skepticism — it lets him tell "the label is genuinely wrong" from "we misread it" in about a second. It is **never** behind a click, a hover, or a disclosure. Panel: `#EFEBE2` fill, `2px #8C877C` border, radius 4px, fixed height (small 84px / medium 110px / large 150px), width 220/340/440px, `overflow: hidden`, centered contents. A 15px mono caption underneath reads `crop · <filename>`.

**Confidence** is text plus a bar, never a bar alone: `Reading confidence 0.91` then a 160 × 12px track (`#E6E1D7`, 2px border) filled `#4A4843` to the percentage, then a word — `(high)` ≥ 0.95, `(good)` ≥ 0.85, `(low — look closely)` below.

**Override.** Accept and Reject are on every row, always visible, 48px tall. Accepted → button fills black; Rejected → button fills `#7A2020`. Overriding inserts a purple panel (`#EDEBFB`, `2px #3B348C`) above the controls and switches the card's left rail to `#3B348C`:

> **Agent decision: Accepted**
> Tool's original verdict was **Fail**. It has been kept on the record alongside your decision.
> Decided by R. Delgado at 10:42 today.
> [ Undo my decision ]

The original verdict is **never** silently replaced. The optional note is a permanently visible input, not a hidden field.

**Government warning block.** Rendered separately below the fields, with more room, since it is the only exact-match check and has the most failure modes.

- Two columns, `1.4fr 1fr`, gap 28px.
- Left: the full detected text in mono 19px/1.7 inside a `#F7F5F1` panel. Any wording that differs from 27 CFR 16.21 is wrapped in `<mark>` (`background: #F6E3A8`, `padding: 0 2px`) — **inline in the text, not in a separate diff view**. Underneath, a 19px sentence that states plainly whether wording matched and, if the verdict is not Pass, names the actual reason. In the sample data nothing is highlighted, and the line reads: *"Nothing is highlighted, because the wording matches the required text exactly. This is marked **Needs review** for one reason only: 'GOVERNMENT WARNING' may not be printed in bold. Look at the crop and decide."* Keep this discipline — the prose must agree with the badge and with the sub-checks.
- Right: the evidence crop of the warning region, min 200px tall.
- Below: five labeled sub-check rows, each `grid-template-columns: 190px 340px 1fr` — badge, check name (19px/600), reason (18px). Passing rows use a neutral `#F7F5F1` fill with `#DDD9D0` border so the non-passing ones stand out; non-passing rows use their verdict tint and border.

  1. Wording matches the required text
  2. "GOVERNMENT WARNING" in capital letters
  3. "GOVERNMENT WARNING" in bold
  4. Size relative to surrounding text
  5. Readable against its background

- Its own Accept / Reject pair at the bottom.

**When opened from a batch:** a bar above the summary with **Back to the batch table** on the left and, on the right, "Label 3 of 200 in this batch" plus **Previous label** / **Next label** — so an agent works the queue without returning to the table.

---

### Screen 4 — Batch: upload

**Primary action:** `Check these 244 labels` — 60px, 22px/700, black fill, with the estimate beside it ("Takes about 9 minutes. You can review results as they arrive.").

Three numbered sections:

1. **Label images** — Choose image files button + live count "247 images selected" (20px/600) + Clear all.
2. **Application spreadsheet** — Choose spreadsheet + "august-imports.csv · 247 rows". Below, a bordered panel: *"Not sure of the column names?"* with a **Download the template spreadsheet (CSV)** button. Nobody should have to guess column names.
3. **Before we start** — pre-flight, computed *before* anything runs. Four stat tiles: 247 images / 247 rows / 244 matched (green) / 3 need attention (amber). Then an amber panel listing every mismatch **specifically, by filename or row number**:
   - "Image **ridgeline-gin-04.jpg** is not named in any spreadsheet row. It will be skipped."
   - "Row **112** (app-11902) names **harbor-vodka-front.jpg**, which is not among the uploaded images. It will be skipped."
   - "Row **187** has no brand name in column B. Brand name is required, so this row cannot be checked."

   Closing line: "You can fix these now and re-upload, or go ahead with the 244 that matched."

Mismatches surface here, never four minutes into a run.

---

### Screen 5 — Batch: progress

**Primary action:** `Review the N problems found so far` — black fill. `Stop this run` is a white secondary, always visible, with "Stopping keeps everything checked so far." beside it.

- Determinate bar, 26px tall: **"47 of 200 labels checked"** (30px/700), with "122 seconds elapsed · about 398 seconds left" on the right.
- Four live count tiles, each glyph + number + word in the verdict tint: passed / need review / failed / could not be read.
- **"Arriving now"** — results stream in as they complete, newest visible immediately, each a row with badge, application ID (mono), brand, and issue summary, with an 8px left rail in the verdict color. An agent starts triaging failures before the run finishes.

---

### Screen 6 — Batch: results table

**Primary action:** `Export all 200 results` — black fill, 60px, top right.

- **Sorted problems-first by default** — fail, then needs review, then pass. This is a stated requirement. An agent must never hunt for failures.
- Filter chips above the table, 52px tall, with counts baked into the label: `All (200)` `Failures (14)` `Needs review (31)` `Passed (155)`. Selected = black fill; set `aria-pressed`.
- A line above the table restates the state in words: "Showing 14 of 200 labels · filter: Failures · sorted with failures first."
- Columns: **Status** (badge, 230px) · **Application** (mono, 180px) · **Brand name** · **Issues** ("2 issues — bottler address, warning" or "—", 280px) · **Label** (62 × 82px thumbnail, 130px) · **Open** (200px).
- Row padding `18px 20px`, generous height, zebra `#FFFFFF` / `#FBFAF8`, 2px `#DDD9D0` row borders. Header row `#EFEBE2`, 17px/700 uppercase, `<th scope="col">`.
- **Open this label** is a real labeled button in the last column — not a bare clickable row, which is invisible to keyboard users. Making the whole row clickable as well is fine as an addition, never as the only way in.

---

### Screen 7 — Errors and unreadable labels

Never a generic failure. Every message states **what happened** and **what to do next**, and where partial results exist they are shown alongside rather than discarded. Each card carries a verdict badge tag, a 23px title, a "what happened" paragraph, a bolded **What to do:** paragraph, two buttons, and a line about partial results.

| Situation | Message | What to do | Partial results |
|---|---|---|---|
| Glare | "A bright reflection covers the lower third of the label, including where the government warning normally sits." | "Re-photograph the bottle without direct light on it — daylight near a window, no flash." | Brand name, class and net contents were read and are shown underneath. |
| Blur | "The text edges are too soft for us to be confident about any field." | "Take a sharper photo from the same angle and distance. Tap the screen on the label before taking it." | Nothing readable; none shown. |
| Resolution | "This image is small — 400 × 300 pixels. Text at this size cannot be read reliably." | "An image 1000 pixels wide or larger works best. Ask the applicant for the original file." | If they proceed, every field is marked Needs review regardless. |
| Cropped | "The frame ends part way down the label. The government warning is usually in this area and may be outside the photo." | "Re-photograph with the whole label in frame, or upload a second photo of the lower portion." | Everything above the cut is shown, marked as read from an incomplete image. |
| Service down | "The service that reads label text is not responding. This is on our side, not yours." | "Try again in a moment. If it keeps happening after ten minutes, tell the help desk." | Everything typed is kept exactly as left. Nothing needs re-entering. |

**Empty states**

- *Single label, nothing entered:* the Check button stays off and the line above names what is missing — "Add a label image and fill in Net contents to continue."
- *Batch filter with no matches:* "No labels failed in this batch. That is good news — switch the filter to Needs review to see the 31 that want a second look."
- *No batches run yet:* "You have not run a batch yet. Start by uploading your label images and the spreadsheet that goes with them." Upload button directly underneath.

---

## Interactions and behavior

- Screen 1 → 2 on submit; 2 → 3 automatically when the check returns. Screen 4 → 5 on submit; 5 → 6 via the review button or on completion. Any table row on 6 → Screen 3 with `fromBatch` set, enabling prev/next and the back link.
- No animated transitions between screens. The only motion in the product is the two progress bars filling. Nothing animates information into view.
- Form fields are controlled and validated live; the missing-items line and button state recompute on every keystroke and on beverage-type change.
- Overrides are per-field and reversible. Notes are per-field free text saved with the override.
- Hover states: none carry information. Pointer cursor and, at most, a border darkening — never a revealed control.
- Focus: the global 3px `#1A4C8B` ring is mandatory. Tab order follows document order, which follows reading order on every screen.

## State

| State | Type | Notes |
|---|---|---|
| `screen` | enum | input / processing / results / batchUpload / batchProgress / batchResults / errors — real routing in production |
| `hasImage`, `file` | bool / File | Screen 1 upload |
| `beverageType` | `Spirits \| Wine \| Malt beverage` | drives conditional requirement of alcohol content |
| `form` | object | brand, class, alcoholContent, netContents, bottler, countryOfOrigin |
| `missingRequired` | derived array | drives both the disabled button and the explanatory line |
| `elapsed` | number | processing seconds; > 10 reveals the slow panel |
| `result` | API response | see data shape |
| `overrides` | `{ [fieldKey]: 'accept' \| 'reject' }` | never mutates the original verdict |
| `notes` | `{ [fieldKey]: string }` | |
| `batchDone`, counts | numbers | polled or streamed during a run |
| `filter` | `All \| Failures \| Needs review \| Passed` | Screen 6 |
| `fromBatch` | bool | shows prev/next + back link on Screen 3 |

## Data shape

The design is built directly against this response; field keys map 1:1 to the row component's props.

```jsonc
{
  "label_id": "app-10482",
  "beverage_type": "spirits",
  "overall": "needs_review",          // pass | needs_review | fail
  "processing_ms": 2310,
  "fields": [
    {
      "field": "alcohol_content",
      "display_name": "Alcohol content",
      "declared": "45% Alc./Vol. (90 Proof)",
      "detected": "45% ALC/VOL (90 PROOF)",
      "verdict": "needs_review",
      "confidence": 0.91,
      "reason": "Formatting differs; values match.",
      "crop_url": "/crops/app-10482/alcohol_content.png",
      "override": null                 // or { decision, note, at }
    }
  ],
  "warning_checks": [
    { "check": "text_exact", "verdict": "pass", "reason": "Matches 27 CFR 16.21 exactly." },
    { "check": "caps",       "verdict": "pass", "reason": "GOVERNMENT WARNING is in capitals." },
    { "check": "bold",       "verdict": "needs_review", "reason": "Stroke weight only slightly above body text." },
    { "check": "proportion", "verdict": "pass", "reason": "Warning text is 92% of body text height." },
    { "check": "contrast",   "verdict": "pass", "reason": "Dark text on light background." }
  ]
}
```

`reason` strings are rendered verbatim — write them as plain sentences an agent can act on, in the engine, not in the UI. `crop_url` must always be present for a field with a verdict; a field without a crop cannot be defended to a skeptical agent.

## Copy voice

Short declarative sentences. No jargon, no error codes, no "oops". Say what happened, then what to do. Numbers spelled as digits. The tool is deferential — it reports and recommends, it never announces a decision. Reuse the exact strings in this README wherever they cover the case.

## Assets

None external. Two Google Fonts (Public Sans, IBM Plex Mono) — substitute the codebase's equivalents only if they are as legible at 19px. Verdict marks are the text characters `✓`, `⚠`, `✕`, not icons; if the codebase has an icon set, an icon may replace the glyph but the word must remain.

## Files

- `Label Check.dc.html` — the full prototype, all seven screens plus a design-reference screen carrying the color table with contrast ratios, the type scale, the badge set, and the field row in all four states (pass, needs review, fail, overridden).

## Self-check before shipping

Walk the nine hard constraints against every screen you built. A build that fails one costs more to rework than it saved.
