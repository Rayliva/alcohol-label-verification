# Build loop — TDD

**Chosen:** TDD loop, with two named exceptions.
**Run with:** `/build`
**Date:** 2026-08-09

---

# CURRENT STATE — read before doing anything

Last updated: 2026-08-09, end of session 3.

## Where we are

**Phases 0–3 are complete and deployed.** Phase 4 is the only phase left, and
every item in it is a documented scope decision rather than an oversight.

283 backend tests and 19 frontend tests, all green, all offline. Lint, format
and mypy clean. Pushed to `main`; Render is serving it.

| Stopping condition | Result |
|---|---|
| p95 < 5s, measured and published | **4,525 ms**, n=20, against the deployed instance |
| Zero false PASS on warning violations | **0** |
| ≥95% field-verdict accuracy | **99.0% end to end**, 100.0% for the rules alone |
| 200-label batch with visible progress | **69 s**, 174/min, determinate throughout |
| All P0 and P1 features shipped | Yes |
| Deployed URL live and verified | <https://alcohol-label-verification-3sn4.onrender.com> — UI, API and batch all verified live |
| README with setup, approach, numbers, limitations | Yes |

### What is built

- `app/rules/` — matchers, six-check government warning, config-driven beverage
  types, engine. Pure; a purity test enforces it
- `app/pipeline/` — quality gate, geometric measurement, evidence crops
- `app/batch/` — manifest parsing, pre-flight, in-memory job store, worker pool
- `app/api/` — single-label and batch routes, typed errors, a 500 backstop
- `app/bench/latency.py` — the harness behind every number in the README
- `web/` — React 19 + Vite, Screens 1–6, built bundle served from the API
- `corpus/` — 61 curated labels, 200-label fixture, malformed manifests,
  ground-truth OCR
- Specs: `docs/specs/rule-engine.md`, `pipeline.md`, `batch.md`

### What is deliberately not built (Phase 4)

Each is argued in the README under "Deliberately not built" — read that before
reopening any of them.

1. **Wine and malt rule content.** The engine reads all three from config and
   the UI disables the other two with the reason attached. Content plus corpus
   labels is the work.
2. **Image preprocessing** — deskew, glare removal. The quality gate detects and
   reports these; correcting them is unbuilt.
3. **Vision escalation.** Would ship only if the corpus showed OCR failing on
   labels a human can read. It does not.
4. **PaddleOCR adapter** — the on-prem answer to the firewall constraint is
   documented and the interface exists; the adapter does not.

## What still needs a human

- **AI-generated tier-1 artwork and real bottle photographs.** The corpus is
  rendered, which is why its ground truth is exact and also why it does not
  stress OCR against foil, curved glass or script faces. Cannot be produced from
  here.
- **A Vercel project** if the frontend should be deployed separately. Today the
  API serves the built bundle from the same origin, which is why one URL is a
  working application.
- **Render dashboard access** for anything that needs the build context to
  change — that is why the frontend bundle is committed under `api/app/static`.

## Environment facts that will otherwise cost you time

- **Windows.** Use `api/.venv/Scripts/python.exe`, not `bin/python`.
- **`uv` was installed via pip** and is not on PATH — invoke it as `python -m uv`.
- Tests: from `api/`, `.venv/Scripts/python.exe -m pytest -q`
- Accuracy suite alone: add `-m accuracy`. Skip it with `-m "not accuracy"`
- Lint: `.venv/Scripts/python.exe -m ruff check app tests ../corpus`
- Frontend: from `web/`, `npm run test` (single pass), `npm run build`
- **`corpus/out/` is gitignored.** Regenerate before anything that needs images:
  `api/.venv/Scripts/python.exe corpus/generate.py --all` and `--batch 200`
- **After any UI change**: `npm run build` in `web/`, then copy `dist` over
  `api/app/static`, or the deployed UI keeps the old bundle
- `tests/conftest.py` forces the suite offline. Do not remove it: with a
  populated `.env`, FastAPI startup warming fires real API calls on every
  TestClient
- Git line-ending warnings on Windows are noise. If a commit is blocked by CRLF
  safety, use `git -c core.safecrlf=false commit`
- Long heredocs through the Bash tool break on quoting. Use the Write/Edit tools
  for anything with nested quotes

## Credentials and deployment

- `.env` exists locally with `ANTHROPIC_API_KEY` and
  `GOOGLE_APPLICATION_CREDENTIALS_JSON`. **Never read, print, or commit it.**
- Render has the same variables plus `OCR_ENGINE=cloud`. **Pushing to `main`
  auto-deploys**, and a deploy takes two to four minutes — measurements taken
  immediately after a push may hit the old build.
- `OCR_ENGINE=fake` runs the entire stack with no credentials and no network.

## Known and accepted

- **Haiku 4.5 prompt cache does not engage.** The system prompt is below that
  model's minimum cacheable prefix. Padding it would be gaming a number.
  Reported on `/health`, published in the README, left alone.
- **Every geometric warning check is a proxy.** 27 CFR 16.22 states absolute
  millimetres, which an uncalibrated photograph cannot supply (PRD OS-7).
  Thresholds were calibrated against the corpus and the measurements are
  recorded beside the constants in `app/rules/warning.py`.
- **Glare on pure-white artwork is undetectable** by luminance: a reflection has
  no headroom above white paper. Documented in `quality.py` and the README.
- **Extraction temperature is pinned at 0.** At the default, the same label got
  different verdicts on different runs.

## Decisions already made — do not relitigate

- **Spirits first**, engine config-driven from day one, wine and malt buttons
  disabled *with the reason attached*.
- **No authentication.** An optional "your name or initials" attributes
  overrides within a session.
- **Nothing is stored.** A restart loses in-flight batch jobs and the API says
  so when asked about one.
- **`unreadable` is a fourth label-level outcome**, produced by the pipeline and
  never by the rule engine.
- **Plain CSS with tokens rather than Tailwind** in `web/`. The design specifies
  exact values and each is an accessibility decision with a reason.
- **Two accuracy numbers are published, not one.** The end-to-end figure hides
  which layer is wrong; the rules-only figure is the flattering one.

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
