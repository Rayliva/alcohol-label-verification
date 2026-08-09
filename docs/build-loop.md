# Build loop — TDD

**Chosen:** TDD loop, with two named exceptions.
**Run with:** `/build`
**Date:** 2026-08-09

---

# CURRENT STATE — read before doing anything

Last updated: 2026-08-09, end of session 1.

## Where we are

**Phase 0: COMPLETE.** All three gates met.

| Gate | Result |
|---|---|
| Model | `claude-haiku-4-5`, thinking `disabled`, effort `low` — pinned in `app/config.py` |
| Latency | p95 **2,528 ms** end-to-end against a 5,000 ms target (n=20) |
| Deploy | Live: https://alcohol-label-verification-3sn4.onrender.com/health |

**Phase 1: IN PROGRESS.** 30 tests passing, lint clean.

Done:
- `app/ocr/` — `OcrEngine` protocol, `CloudVisionEngine`, `FakeOcrEngine`, factory
- `app/extraction/` — structured-output client, capability handling per model generation
- `app/rules/types.py` — `Verdict`, `FieldResult`
- `app/rules/normalize.py` — `normalize()` and `normalize_whitespace_only()`
- `app/rules/match_text.py` — token-aware fuzzy matching
- `app/main.py` — FastAPI, `/health`, three-stage startup warming
- `api/Dockerfile`, deployed and verified

## Next behaviours, in order

Work the TDD loop below. Each is one or more iterations.

1. **`app/rules/match_abv.py`** — parse ABV to a number; cross-check `proof = 2 x ABV`
   (`45% Alc./Vol. (90 Proof)`). Regulatory tolerances are label-vs-liquid, **not**
   form-vs-label — any form/label difference is at minimum NEEDS_REVIEW. See
   `.claude/rules/verify-regulations.md`.
2. **`app/rules/match_volume.py`** — parse value + unit, normalise to mL
   (`750 mL` = `75 cL` = `0.75 L`).
3. **`app/rules/warning.py`** — the five sub-checks: exact text (whitespace-normalised
   only, never case-folded), `GOVERNMENT WARNING` in capitals, bold via relative stroke
   weight, proportional size vs `OcrResult.median_text_height`, contrasting background.
4. **`app/rules/beverage_types/spirits.py`** — config-driven required-field set.
   Engine reads config from the first commit; only spirits is populated (wine and malt
   are Phase 4).
5. **`corpus/generate.py`** — the real tiered corpus. `corpus/render.py` currently
   renders only 3 spike samples and has no `corpus/fixtures/expected.json`. This is a
   gap; the accuracy target cannot be measured until it exists. See PRD → Test corpus.
6. **Pipeline assembly** — `image -> ocr -> extract -> rules -> FieldResult[]`, plus
   evidence crops from bounding boxes.
7. **API routes** then **Phase 2 UI**.

## Environment facts that will otherwise cost you time

- **Windows.** Use `api/.venv/Scripts/python.exe`, not `bin/python`.
- **`uv` was installed via pip** and is not on PATH — invoke it as `python -m uv`.
- Run tests from `api/`: `.venv/Scripts/python.exe -m pytest -q`
- Lint: `.venv/Scripts/python.exe -m ruff check app`
- **`corpus/out/` is gitignored.** Regenerate images with
  `api/.venv/Scripts/python.exe corpus/render.py` before anything that needs them.
- Optional deps are extras: `python -m uv sync --extra server --extra cloud-ocr`
- Git line-ending warnings on Windows are noise. If a commit is blocked by CRLF
  safety, use `git -c core.safecrlf=false commit`.

## Credentials and deployment

- `.env` exists locally with `ANTHROPIC_API_KEY` and `GOOGLE_APPLICATION_CREDENTIALS_JSON`.
  **Never read, print, or commit it.**
- Render has the same variables plus `OCR_ENGINE=cloud`. **Pushing to `main`
  auto-deploys.**
- `OCR_ENGINE=fake` runs the entire stack with no credentials and no network — use it
  for all tests.

## Known and accepted

- **Haiku 4.5 prompt cache does not engage.** The system prompt is below that model's
  minimum cacheable prefix. Documented in the README, surfaced in `/health` notes.
  Accepted — do not pad the prompt to game the threshold.
- **`/health` "degraded" means actionable.** Known conditions go in `notes`.

## Decisions already made — do not relitigate

- **Spirits first.** Wine and malt rule sets are Phase 4, but the engine reads beverage
  config from day one. Wine/malt buttons ship **disabled with an explanation**.
- **No authentication.** An optional "your name or initials" field attributes overrides
  within a session. Rationale in README → Production considerations.
- **`unreadable` is a fourth label-level outcome**, separate from `fail`.
- **`crop_url` is nullable** — a field absent from the label has no region to crop.
- UI design handoff is at `docs/design/design_handoff_label_check/`. Nine review
  resolutions are recorded in `docs/ui-spec.md` → Resolutions from design review; the
  handoff README predates them, so **`ui-spec.md` wins on conflict**.

---

The build is mostly one task repeated: encode a regulation, prove it holds. That is the TDD cycle, so it is the spine of the procedure.

---

## Phase 0 — Spike (manual, runs once, before anything else)

**This phase is not TDD.** You cannot write a failing test for "which model is fastest." It is a measurement experiment, and it comes first because latency is the top risk in the PRD and its answer constrains everything downstream.

1. Thinnest possible pipeline: image → OCR → LLM extraction → print JSON. No UI, no rules, no batch.
2. Run [`benchmark-latency`](../.claude/skills/benchmark-latency.md) across `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`.
3. Measure `thinking: disabled` against `adaptive` + `effort: low`.
4. Get per-stage timings — preprocess, OCR, LLM, rules.
5. Deploy the stub to Render and Vercel. **Prove the deploy path works on day one**, not on day six.

**Exit criteria:** a model pinned in `EXTRACTION_MODEL`, a measured p95, a live public URL, and the comparison table drafted for the README.

**If p95 > 5s at this point, stop and redesign.** Do not build a UI on a pipeline that cannot meet its headline requirement.

Spike code is then deleted or promoted into `app/bench/`. It does not survive as production code without tests.

---

## The loop (Phases 1–4)

Each iteration handles **one behavior**, not one feature.

```
1. SELECT   Take the next behavior from docs/specs/<feature>.md, in priority order.
            No spec? Write one first (.claude/rules/spec-driven-development.md).

2. TRACE    Confirm it maps to requirements.md or a numbered PRD item.
            Neither? Stop and propose. (.claude/rules/trace-to-brief.md)

3. VERIFY   Compliance behavior? Check the CFR section against a primary source
            and cite it. Never from memory. (.claude/rules/verify-regulations.md)

4. RED      Write one failing test naming the observable outcome.
            Run it. Confirm it fails for the RIGHT reason, not an import error.

5. GREEN    Minimum code to pass. No speculative abstraction.

6. REFACTOR Clean up with the test as a safety net. Tests stay green.

7. CORPUS   Compliance behavior? Add the label variant covering it,
            with expected verdicts. (skills/generate-corpus.md)

8. CHECK    uv run pytest
            Touched rules/ or thresholds? Also: pytest api/tests/accuracy -m accuracy

9. COMMIT   One behavior per commit. Message cites the FR or CFR section.

10.         Next behavior.
```

## Build order

Priority follows the PRD, with one deviation: batch comes before polish because it is the largest untested surface.

| Phase | Content | Loop applies |
|---|---|---|
| **0** | Spike — model choice, latency, deploy path | Manual |
| **1** | Corpus generator, then the rule engine **for spirits**: matchers, normalizers, warning checks. Config-driven from the first commit | **Full TDD.** ~40 iterations, the bulk of the build |
| **2** | Pipeline integration, evidence crops, single-label API + UI | TDD for logic; UI per the exception below |
| **3** | Batch mode, override, export | TDD for the job store and manifest parsing |
| **4** | Wine + malt rule sets and corpus labels · image preprocessing · proportional/bold checks · README and measured numbers | TDD where testable |

Phase 1 first is deliberate: `rules/` is pure and needs no network, no UI, and no OCR to develop against. It is the highest-value, fastest-feedback work in the project.

**Spirits first, config-driven throughout.** The engine reads beverage rule sets from config starting with the first commit — only `spirits.py` is populated until Phase 4. Sequencing the *content* de-risks; sequencing the *architecture* would create a retrofit. See PRD → Sequencing.

**UI design happens during Phase 1**, in parallel. The rule engine is headless, so design work costs no serial time. See `docs/ui-spec.md`; Phase 2 implements it.

---

## The two exceptions

**Phase 0 spike — manual.** Above. Exploratory measurement, no tests.

**UI work — partial.** The nine requirements in [`accessibility.md`](../.claude/rules/accessibility.md) are testable and get tests (role queries, target size, contrast). Visual layout and spacing do not — build, then verify in a browser. Do not fake a test for a behavior a test cannot observe.

Everything else, including anything touching `rules/`, is full TDD with no exceptions.

---

## Stopping condition

Done when all of:

- [ ] p95 < 5s, measured and published
- [ ] Zero false PASS on government warning violations across the corpus
- [ ] ≥95% field-verdict accuracy on the ~61-label curated corpus
- [ ] 200-label batch completes with visible progress
- [ ] All P0 and P1 features from the PRD shipped
- [ ] Deployed URL live and verified cold
- [ ] README carries setup, approach, measured numbers, and documented limitations

P2 items ship only if the above are all green.

---

## Failure handling

| Situation | Response |
|---|---|
| Test fails for the wrong reason | Fix the test first. A test that fails on an import error proves nothing. |
| Implementation reveals the spec was wrong | **Stop.** Fix the spec, get sign-off, then resume. Do not silently code around it. |
| Accuracy suite regresses after a threshold change | Do not move the threshold until it passes. Decide whether the change or the expectation is wrong. |
| Stuck > 30 min on one behavior | Stop. State the blocker and the options. Do not thrash. |
| Behavior traces to nothing in the brief | Stop and propose before building. |
| A CFR value cannot be verified | Mark `TODO: unverified`. Never fill the gap with a plausible number. |
| Scope pressure late in the week | Cut P2 first, then P1 extras. Never cut tests, and never cut the measured numbers — an honest gap outscores a silent one. |
