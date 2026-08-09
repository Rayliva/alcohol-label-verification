# Build loop — TDD

**Chosen:** TDD loop, with two named exceptions.
**Run with:** `/build`
**Date:** 2026-08-09

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
