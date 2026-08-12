# PRD — AI-Powered Alcohol Label Verification

**Status:** Draft, bootstrap Phase 1
**Date:** 2026-08-09
**Source of truth:** [`requirements.md`](../requirements.md) — the original take-home brief, verbatim. Where this PRD and the brief disagree, the brief wins.

---

## Summary

A standalone web application that verifies alcohol beverage label artwork against the data declared in a TTB COLA application. An agent supplies a label image and the declared field values; within about five seconds the tool returns a per-field verdict — PASS, NEEDS REVIEW, or FAIL — with the cropped region of the image that justifies each call. The agent confirms or overrides. The tool advises; it never decides.

Supports single-label review and batch submissions of 200–300 labels. Covers distilled spirits, wine, and malt beverages through a data-driven rule set.

---

## Problem

TTB reviews roughly 150,000 label applications a year with 47 agents. Each review is a manual, visual field-by-field comparison of artwork against declared data, taking 5–10 minutes. Three problems compound:

1. **Routine burden.** Roughly half of agent time is mechanical matching — confirming the number on the form equals the number on the label. This crowds out the judgment work only a human can do.
2. **Throughput.** ~3,200 applications per agent per year, with peak-season batches of 200–300 arriving at once and processed one at a time.
3. **Escaped violations.** Subtle non-compliance slips past visual review — title-case warning statements, disproportionately small warning text, an ABV off by a digit.

The tool targets all three. Speed and accuracy are not traded against each other.

---

## Users / personas

**Primary user for v1: the take-home evaluator.** v1 is sized to demonstrate the core loop convincingly, not to carry division-wide production volume.

The TTB personas remain binding design constraints, because the evaluation rubric scores against them:

| Persona | Relevance |
|---|---|
| **Dave Morrison** — senior agent, 28 years, low tech comfort, skeptical of modernization | Drives the explainability and override requirements. A verdict without visible reasoning gets ignored. |
| **Jenny Park** — junior agent, 8 months, high fluency | Drives the exact-match warning check and imperfect-image handling. |
| **Sarah Chen** — Deputy Director, sponsor not daily user | Drives batch mode and the 5-second latency budget. |
| **"My 73-year-old mother"** — Sarah's stated usability bar | Large targets, obvious labels, one primary action per screen, no hidden state. |

---

## Goals & success metrics

| Metric | Target |
|---|---|
| Single-label latency | **p95 < 5 seconds**, measured and published in the README |
| False PASS on government warning violations | **Zero** — a missed violation is the expensive error; a false flag costs ten seconds |
| Field verdict accuracy | **≥ 95%** across the curated test corpus (~370 field verdicts) |
| Batch reliability | **200 labels complete without failure**, progress visible throughout |

Rationale for the asymmetry: false FAILs cost an agent seconds. False PASSes let non-compliant product reach market.

---

## In-scope features (prioritized)

### P0 — Core loop

1. **Single-label review.** Upload artwork, enter declared fields, receive per-field verdicts.
2. **Field extraction** from label imagery: brand name, class/type, alcohol content, net contents, bottler/importer name and address, government warning.
3. **Three-state field verdicts** — PASS / NEEDS REVIEW / FAIL, never binary. Each carries a confidence score.

   At the **label** level there is a fourth outcome, `unreadable`, for images that could not be processed (FR-15). It is deliberately not folded into FAIL: "we could not read this" is not "this label is non-compliant," and conflating them would report compliant labels as violations and corrupt every accuracy number we publish. Batch counts and filters carry it as its own bucket.
4. **Evidence crops.** Every verdict shows the declared value, the detected value, and the region of the image it came from — so an agent can distinguish a genuine discrepancy from an OCR misread at a glance.
5. **Government warning verification** (exact, per 27 CFR 16.21/16.22):
   - Verbatim text match after whitespace normalization — no fuzzy matching
   - `GOVERNMENT WARNING` in capital letters
   - `GOVERNMENT WARNING` in bold, via relative stroke-weight analysis
   - Proportional size check — warning text height relative to surrounding text
   - Contrasting background
6. **Fuzzy matching** for all non-warning text fields: normalize case, whitespace, quote characters, accents, and trailing punctuation, then score by normalized edit distance with token-aware handling of dropped corporate suffixes.
7. **Numeric matching** for ABV and net contents: parse to values and units, normalize (mL as base), compare numerically. Cross-check proof = 2 × ABV.
8. **Deployed public URL** with no cold-start penalty.

### P1 — Required by the brief

9. **Batch mode.** Multi-image upload plus CSV/JSON manifest pairing images to application records. Live progress. Results table sorted problems-first.
10. **Agent override.** As shipped (revised 2026-08-11/12, docs/ui-spec.md
    Sessions 6-7): the agent decides once per application — Approve or
    Reject, with an optional note — on the review screen or directly on a
    fresh upload's results. Approving a flagged application is recorded as
    an override. Per-field accept/reject was built, then removed: it asked
    the same question up to seven times per label. Decisions live in the
    in-memory queue for the session and are not stored (C-2); the batch CSV
    export carries verdicts, not decisions.
11. **Imperfect image handling.** Preprocessing for skew, low light, and glare. When a label genuinely cannot be read, report the specific reason rather than failing generically.

### P2 — Deliberate additions beyond the brief

12. **Results export** — CSV/JSON download. *Not requested in the brief; added by decision.*
13. **Same-field-of-vision check.** For spirits, 27 CFR 5.63 requires brand name, class/type, and alcohol content to appear on the same side of the container. Verifiable from OCR bounding boxes.

---

## Beverage-type rules (from TTB research)

The rule set is data-driven. Beverage types are configuration, not code paths.

| Field | Spirits (Pt. 5) | Wine (Pt. 4) | Malt (Pt. 7) |
|---|---|---|---|
| Brand name | Required | Required | Required |
| Class/type | Required | Required | Required |
| Alcohol content | Required | **Conditional** | **Conditional** |
| Net contents | Required | Required | Required |
| Bottler/importer name & address | Required | Required | Required |
| Government warning | Required | Required | Required |

**Conditionals:**

- **Wine ≤ 14% ABV** may omit the percentage if the label states "table wine" or "light wine." Above 14%, mandatory.
- **Malt beverages** require ABV only when alcohol derives from added nonbeverage flavors or ingredients.

A hardcoded spirits engine would emit false violations on two of three categories.

### Sequencing: spirits first, architecture config-driven from day one

These are separate decisions and only one of them is deferred.

**Not deferred — the engine reads rule sets from config starting with the first commit**, even while only `spirits.py` exists. Nearly free upfront, expensive to retrofit; the trap is hardcoding spirits behavior and then finding that wine's conditional ABV doesn't fit the shape already built.

**Deferred — wine and malt rule sets and their corpus labels move to Phase 4.** Spirits is the type the brief exemplifies and the only one with no ABV conditional, so it validates the whole pipeline with the fewest moving parts.

Trade-off, stated plainly: if the week runs short we ship spirits complete with a documented gap, rather than three beverage types half-finished. That is the better failure mode and matches the brief's preference for a working core over incomplete ambition.

**Statutory warning text (27 CFR 16.21), verbatim:**

> GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.

One continuous statement; `(1)` and `(2)` are inline.

**Type size (§16.22), for documentation only — not verifiable from an uncalibrated image:**

| Container | Min type size | Max chars/inch |
|---|---|---|
| ≤ 237 mL | 1 mm | 40 |
| > 237 mL – 3 L | 2 mm | 25 |
| > 3 L | 3 mm | 12 |

**ABV tolerance note.** Regulatory tolerances (spirits ±0.3 points; wine ±1.5 at ≤14%, ±1.0 above) govern label versus *actual liquid*, lab-verified. They are **not** tolerances between application and label — both are documents and should agree. Any form-to-label ABV difference is at minimum NEEDS REVIEW, with the regulatory tolerance surfaced to the agent as context, never as a pass rule.

---

## Test corpus

**Two sources, chosen per tier.** Ground truth never comes from what we *asked* a generator for — it comes from what the label actually says. For rendered labels the generator knows that by construction; for AI-generated labels it is read off the image and recorded in the fixture. A brand rendered as "Raychel's Brewery" is fine — the fixture declares "Raychel's Brewery" and the expected verdict is PASS.

Rendering is required only where the tier needs **surgical control or volume**:

- **The government warning.** ~50 words of statutory text, needed byte-perfect in one variant and altered by exactly one word in another. Image models drop words and mangle the `(1)`/`(2)` numbering; an incorrect "correct" variant makes the test assert the opposite of what it claims.
- **Parameterized violations** — warning at 40% of body-text height, title case, ABV/proof mismatch.
- **Volume** — 200 batch labels, instant and free to render.

AI generation is *better* for clean baselines and realism, because rendered labels are synthetic and don't stress OCR against real typography, foil, or curved surfaces.

**Design principle: one violation per label.** Multi-violation labels are included only for realism, not for diagnosis.

| Tier | Purpose | Count | Source | Contents |
|---|---|---|---|---|
| 1 | Clean baseline | 12 | **Rendered** (as built — `corpus/generate.py`; the planned AI-generated artwork became the separate unscored smoke set, which is absent) | Realistic artwork, fully compliant |
| 2 | Single-field violations | 28 | Rendered | Brand 5 · class/type 3 · ABV 5 · net contents 4 · bottler 3 · warning 8 |
| 3 | Conditional rules | 6 | Rendered | Wine/malt ABV conditionals, both directions |
| 4 | Image quality | 12 | Rendered, degraded programmatically | 6 degraded-but-readable, 6 genuinely unreadable |
| 5 | Same field of vision | 3 | Rendered | ABV relocated to back label |
| **Curated total** | **Scored** | **~61** | | ≈370 field verdicts |
| 6 | Batch fixture | 200 | Rendered | Permutations of tiers 2–3; throughput only |
| 7 | Malformed manifests | 4 | n/a | Missing image, orphan image, bad row, wrong columns |
| — | Smoke set | ~6 | AI-generated + real photos | Realism check; **not scored** |

The warning receives the most coverage of any field — 8 labels spanning verbatim-correct, title case, one word altered, missing, not bold, disproportionately small, low contrast, and paraphrased.

Tier 4 splits deliberately: the tool must succeed on degraded-but-readable images and must fail *with a specific reason* on unreadable ones. Testing only the former rewards confident hallucination.

Real photographs serve as qualitative smoke tests only, excluded from the accuracy score because their ground truth is uncertain.

---

## Out of scope

| # | Excluded | Reason |
|---|---|---|
| 1 | Accounts, user management, password reset | Not required for a prototype; large build cost. A single shared agent credential *is* built, because the deployed URL is public — a gate, not an identity system |
| 2 | Persistent storage / document retention | Brief: "not storing anything sensitive." Revisit only if core lands early |
| 3 | COLA integration | Explicitly ruled out in the brief |
| 4 | Multiple roles, per-agent queue assignment | Assignment belongs to COLA, which is out. One role, one shared queue. No applicant persona: the brief has no such user, and inventing one to justify a portal is scope it cannot defend |
| 5 | Analytics, reporting, audit history | Not requested |
| 6 | Native mobile | Desktop web only; agents work at desks |
| 7 | Absolute millimetre type-size verification | Physically underivable from an uncalibrated image. Proportional check ships instead |

On (7): calibration via an agent-entered label width was considered and rejected. The proportional check already catches the real abuse pattern — nobody shrinks a warning to 95% of the minimum — and adding a field to the primary flow fights the usability bar, which is a scored criterion.

---

## Constraints

| Constraint | Detail |
|---|---|
| **Latency** | ~5 seconds per label. The brief's most emphasized number, with a failure story attached: a prior vendor pilot took 30–40s and agents abandoned it |
| **No sensitive data** | Stateless or ephemeral-session only |
| **Network** | TTB's firewall blocks many outbound domains, which conflicts with the required public deployment URL. Documented with a mitigation path, not solved |
| **Deployment** | A working public URL is a hard deliverable |
| **Stack** | Any language or framework. The .NET/Azure/FedRAMP context is background, not a requirement |
| **Time** | About one week |

---

## Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Latency exceeds 5s** — a single vision-LLM call typically runs 4–10s | **Top risk** | Spike and measure before building any UI. Hybrid design: fast deterministic OCR path, escalate to vision only for hard cases. Concurrency in batch |
| Cold starts on deployed hosting | High | Choose hosting without cold starts, or keep warm. Decide early; it sabotages the evaluator's first click |
| OCR fails on real label typography — script fonts, embossing, foil, curved surfaces | High | Corpus includes genuinely hard labels. Confidence thresholds tuned against it |
| Fuzzy thresholds arbitrary, causing false FAILs | Medium | Tune against the labeled corpus. Publish the values and the method |
| Scope creep | Medium | Core loop deployed and working before P1 begins |

---

## Open questions

1. **Tech stack, OCR/vision approach, hosting** — deferred to bootstrap Phase 2 (`/tech-interview`). Latency is the deciding factor.
2. **Fuzzy match thresholds** — starting points 0.95 PASS / 0.80 NEEDS REVIEW. Placeholders until tuned empirically. Not shipped as unvalidated magic numbers.
3. **Persistence** — parked. Revisit only after the core loop is deployed and working.
4. **Bold prohibition** — the regulation requires `GOVERNMENT WARNING` to be bold; whether bold is *prohibited* in the remainder is unconfirmed. We verify the requirement, not the converse.
5. **Beer and wine label design references** — spirits is the only type the brief exemplifies. Wine and malt corpus designs need sourcing.

---

## Sources

- [27 CFR 16.21 — Mandatory label information](https://www.law.cornell.edu/cfr/text/27/16.21)
- [27 CFR 16.22 — General requirements (type size, bold, contrast)](https://www.law.cornell.edu/cfr/text/27/16.22)
- [27 CFR 5.63 — Mandatory label information, distilled spirits](https://www.law.cornell.edu/cfr/text/27/5.63)
- [27 CFR 5.65 — Alcohol content, distilled spirits](https://www.law.cornell.edu/cfr/text/27/5.65)
- [27 CFR 4.32 — Mandatory label information, wine](https://www.law.cornell.edu/cfr/text/27/4.32)
- [27 CFR 4.36 — Alcohol content, wine](https://www.law.cornell.edu/cfr/text/27/4.36)
- [27 CFR 7.63 — Mandatory label information, malt beverages](https://www.law.cornell.edu/cfr/text/27/7.63)
