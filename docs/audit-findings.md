# Audit findings — 2026-08-11

Four independent audits were run against the codebase with no context from the
working session: requirements coverage, security, logic and correctness, and
documentation accuracy. Status is maintained here, and **fixed** entries stay,
so the record of what was wrong survives the fix.

---

## A. False PASS — a non-compliant label passing

The error class this project exists to prevent. These come first, always.

| # | Status | Finding |
|---|---|---|
| A1 | **fixed** | **Import markers are too narrow.** `rules/engine.py` matches only "IMPORTED BY" and "IMPORTED FROM". Real labels read "IMPORTED AND BOTTLED BY", "SOLE U.S. IMPORTER", "IMPORTED EXCLUSIVELY BY". Those skip the country-of-origin check entirely, and the field never appears in the report, so the agent is not told it was skipped |
| A2 | **fixed** | **A missing warning can be reported as unreadable.** The glare gate in `pipeline/quality.py`: on artwork whose background is pure white the threshold clamps to 255, so a blank bottom margin — a label that simply omits its government warning — satisfies both washed-strip conditions and raises `glare_obscures_text`. The label is never checked and the 16.21 violation is never reported. This is the inversion the module's own comment claims to prevent |
| A3 | **fixed** | **Volume tolerance is a real allowance.** `SAME_SYSTEM_TOLERANCE` in `rules/match_volume.py` is relative (0.1%) and the comment calls it float slack. For a 1 L bottle it permits 1 mL: declared 1000 mL against a label printing 1001 mL returns PASS, with a reason asserting the volumes are the same |
| A4 | **fixed** | **`field_of_vision` passes on a false premise.** When two of its three fields are absent the survivor set has one member, so it emits PASS stating all three appear on the same side. Separately, `pipeline/measure.py` stamps every field "front" on any image narrower than 1.25:1, so the check cannot fail on a single-panel photo — a measurement that could not be taken, reported as satisfied |
| A5 | **open** | **Conditional fields skip silently when both documents are blank.** Unreachable today (wine and malt are unavailable) but becomes a false PASS the moment wine ships: wine over 14% with no ABV anywhere, malt with added nonbeverage alcohol. The corpus already contains `t3-wine-over-14-abv-missing` |

## B. False FAIL — a compliant label accused

| # | Status | Finding |
|---|---|---|
| B1 | **fixed** | `parse_net_contents` sums every metric quantity it finds. Intended for "1 L 500 mL"; also doubles "70 cl 700 ml" (one volume, two spellings, a normal convention on imports) to 1400 mL |
| B2 | **fixed** | `CROSS_SYSTEM_TOLERANCE` (1%) is too tight for "1 PT 9 FL OZ" = 739.34 mL against a declared 750 mL — 1.42% apart, so it fails. That form is named in the module's own docstring as a real one |
| B3 | **accepted** | Aspect ratio alone flips `field_of_vision`: 1000x1400 passes, 1400x800 fails. Real, but not fixed — the corpus renders genuine two-panel artwork at 1.43 and a single-panel landscape export sits at 1.75, so the ratio cannot separate them. Declining to judge whenever the frame is wide would drop the check on every genuine two-panel label, which costs more than the error it prevents. Documented at the call site |

## C. Wrong status or inconsistent output

| # | Status | Finding |
|---|---|---|
| C1 | **fixed** | `anthropic.APIError` derives from `Exception`, not from `OSError`/`RuntimeError`/`ValueError`, so every provider outage, 429, 401 and timeout falls past the 502 handler in `api/routes.py` to the generic 500 backstop |
| C2 | **open** | `pipeline/run.py` recomputes `overall` from untempered warning checks after `temper_by_reading` downgrades the field, so a response can carry `overall: fail` with no field at FAIL |
| C3 | **open** | `find_block`'s last-resort match accepts any block sharing half the words — one word for a two-word value. The evidence crop can be an unrelated line, and `temper_by_reading` then draws its confidence from that wrong block |

## D. Documentation that is false

| # | Status | Finding |
|---|---|---|
| D1 | **open** | README Docker command cannot start the app — it predates the agent credentials that `main.py` requires at boot. `docker-compose.yml` already carries the correct form. This is the first thing an evaluator tries |
| D2 | **open** | README setup omits `AGENT_USERNAME`/`AGENT_PASSWORD` from the env-var table, so following it produces an app that will not boot |
| D3 | **open** | Test counts wrong throughout: README says 285 and 166 rule-engine, `build-loop.md` says 283. Actual 361 collected, 181 rule-engine |
| D4 | **open** | `docs/tech-spec.md`, `docs/ui-spec.md` and `docs/build-loop.md` all still state "no authentication, no accounts, no sessions". `CLAUDE.md` points at build-loop as the current state |
| D5 | **open** | `CLAUDE.md`: "`OCR_ENGINE=fake` runs the whole stack offline" — false twice over. Only the test suite is credential-free |
| D6 | **open** | `docs/tech-spec.md` claims Tailwind and TanStack Query (neither installed), OpenCV as the driving reason for the container (never imported), GitHub Actions, `/metrics`, Playwright, pre-commit, ESLint — none exist. `.claude/skills/add-ui-component.md` repeats the Tailwind error |
| D7 | **open** | `.claude/skills/` — `run-tests.md`, `generate-corpus.md`, `benchmark-latency.md`, `deploy.md` carry wrong paths, flags that do not exist, and a Render env-var table missing the credentials that gate startup |
| D8 | **open** | `samples/README.md` and README point at `samples/labels/`; the 31 labels live in `api/app/samples/` |
| D9 | **open** | `docs/specs/review-queue.md` still says "draft, awaiting sign-off. No code written against this yet" — it is fully implemented |
| D10 | **open** | ~50 citations (`FR-15`, `C-2`, `NFR-1`, `D-5`) reference a PRD numbering scheme the PRD does not define. `.claude/rules/trace-to-brief.md` requires tracing to numbered PRD items and its own example cites two that do not exist |
| D11 | **open** | README Approach diagram carries superseded stage timings against its own measured table; `build-loop.md` publishes the pre-2026-08-11 p95 and throughput |

## E. Gaps the requirements audit named

| # | Status | Finding |
|---|---|---|
| E1 | **open** | No automated latency guard. The brief's headline number has no assertion anywhere; `app/bench/` prints and is not collected by pytest. A regression to 30 s breaks no test |
| E2 | **open** | Batch is tested at 3 labels against a 200-300 requirement, and the default concurrency path is never executed |
| E3 | **open** | The frontend uploads every image twice — preflight posts the full FormData, then start posts it again, and preflight re-fires on every input change |
| E4 | **open** | `extract_from_image` is dead code. Its own module advertises two paths; the vision escalation path has no callers. The README is honest about this; the code is not |
| E5 | **open** | Degraded-image accuracy is unmeasured. The accuracy suite excludes degraded labels by construction, and the one test covering them swallows `CorpusMissingError` and passes without executing an assertion |
| E6 | **open** | UI: a green PASS badge renders on a field the agent just rejected; field overrides say "goes on the record" but are component state discarded on navigation |
| E7 | **open** | The queue screen does not disclose that seeded verdicts were pre-computed. The README does; the screen an evaluator lands on does not |

## F. Fixed on 2026-08-11

| Finding | |
|---|---|
| Session cookie not `Secure` in production | Derived from the CORS origin string, which on the deployed instance still began with `http://localhost`. Own `INSECURE_COOKIES` switch now, off by default |
| Login 500 on any non-ASCII byte | `compare_digest` raises `TypeError` on non-ASCII `str`. Would have locked everyone out permanently had the deployed password contained one. Compared as bytes |
| CSV formula injection in the batch export | Both ends attacker-reachable; an agent opens the file in Excel |
| `concurrency` unvalidated | 0 or negative returned 200 then killed the pool, leaving the job at 0 forever. Bounded 1 to 16 |
| Decompression-bomb window | Pillow only raises above twice its limit; `MAX_IMAGE_PIXELS` set to 50M |

## G. Asserted but did not reproduce

Recorded so it is not re-investigated.

- **Skew as a live false FAIL.** Claimed `t4-skew` produces a stroke ratio of 0.766 and fails. With real OCR the ratio is `None` — the measurement is not produced at all, and the check already asks for review. The 0.766 came from an oracle bounding box, not the pipeline.
- **ZIP handling.** There is no `zipfile` or `tarfile` anywhere; batch takes multipart images plus a manifest. Zip-slip and archive bombs are not applicable.

## Standing note

`CORS_ORIGINS` on the deployed instance is still `http://localhost:5173`. The UI
is same-origin in production, so it is not needed there at all.
