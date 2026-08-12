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
| B3 | **fixed** | Aspect ratio alone decided which panel a field sat on, so 1000x1400 passed and 1400x800 failed with a citation invented by the frame. It cannot be measured away — the corpus renders genuine two-panel artwork at 1.43 and a single-panel landscape export sits at 1.75 — so the verdict was softened instead: a split is NEEDS_REVIEW carrying where each field was seen, never FAIL. Nothing is missed; the check stops asserting what the picture cannot tell it |

## C. Wrong status or inconsistent output

| # | Status | Finding |
|---|---|---|
| C1 | **fixed** | `anthropic.APIError` derives from `Exception`, not from `OSError`/`RuntimeError`/`ValueError`, so every provider outage, 429, 401 and timeout falls past the 502 handler in `api/routes.py` to the generic 500 backstop |
| C2 | **open** | `pipeline/run.py` recomputes `overall` from untempered warning checks after `temper_by_reading` downgrades the field, so a response can carry `overall: fail` with no field at FAIL |
| C3 | **fixed** | `find_block` could attach the wrong evidence twice over: the last-resort match accepted any block sharing half the words (now two thirds), and matching kept whitespace while Cloud Vision joins wrapped lines without a space, so a two-line brand title could never match and the crop fell through to the bottler line that mentions the name. Made visible by the 006 sample. Matching is whitespace-blind now, and blocks that together are exactly the value beat a line that merely contains it |

## D. Documentation that is false

| # | Status | Finding |
|---|---|---|
| D1 | **fixed** | README Docker command cannot start the app — it predates the agent credentials that `main.py` requires at boot. `docker-compose.yml` already carries the correct form. This is the first thing an evaluator tries |
| D2 | **fixed** | README setup omits `AGENT_USERNAME`/`AGENT_PASSWORD` from the env-var table, so following it produces an app that will not boot |
| D3 | **fixed** | Test counts wrong throughout: README said 285 and 166 rule-engine, `build-loop.md` 283. Now 415 collected, 212 rule-engine, 20 frontend, corrected in both |
| D4 | **partly fixed** | `docs/ui-spec.md` and `docs/build-loop.md` corrected. `docs/tech-spec.md` still states "no authentication, no accounts, no sessions" |
| D5 | **open** | `CLAUDE.md`: "`OCR_ENGINE=fake` runs the whole stack offline" — false twice over. Only the test suite is credential-free |
| D6 | **open** | `docs/tech-spec.md` claims Tailwind and TanStack Query (neither installed), OpenCV as the driving reason for the container (never imported), GitHub Actions, `/metrics`, Playwright, pre-commit, ESLint — none exist. `.claude/skills/add-ui-component.md` repeats the Tailwind error |
| D7 | **open** | `.claude/skills/` — `run-tests.md`, `generate-corpus.md`, `benchmark-latency.md`, `deploy.md` carry wrong paths, flags that do not exist, and a Render env-var table missing the credentials that gate startup |
| D8 | **open** | `samples/README.md` and README point at `samples/labels/`; the 31 labels live in `api/app/samples/` |
| D9 | **fixed** | `docs/specs/review-queue.md` said "draft, awaiting sign-off. No code written against this yet" while fully implemented |
| D10 | **open** | ~50 citations (`FR-15`, `C-2`, `NFR-1`, `D-5`) reference a PRD numbering scheme the PRD does not define. `.claude/rules/trace-to-brief.md` requires tracing to numbered PRD items and its own example cites two that do not exist |
| D11 | **fixed** | README Approach diagram carried superseded stage timings against its own measured table; `build-loop.md` published a stale p95. Both republished from the 2026-08-11 run |

## E. Gaps the requirements audit named

| # | Status | Finding |
|---|---|---|
| E1 | **open** | No automated latency guard. The brief's headline number has no assertion anywhere; `app/bench/` prints and is not collected by pytest. A regression to 30 s breaks no test |
| E2 | **open** | Batch is tested at 3 labels against a 200-300 requirement, and the default concurrency path is never executed |
| E3 | **open** | The frontend uploads every image twice — preflight posts the full FormData, then start posts it again, and preflight re-fires on every input change |
| E4 | **open** | `extract_from_image` is dead code. Its own module advertises two paths; the vision escalation path has no callers. The README is honest about this; the code is not |
| E5 | **open** | Degraded-image accuracy is unmeasured. The accuracy suite excludes degraded labels by construction, and the one test covering them swallows `CorpusMissingError` and passes without executing an assertion |
| E6 | **fixed** | UI: a green PASS badge rendered on a field the agent had just rejected, and field overrides claimed a note "goes on the record" in a product that keeps no record. The badge is now an agent mark naming the decision, the controls appear only on flagged fields, and the copy says the decision reaches the CSV export and nothing else. Still component state, and now says so |
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

## Decisions confirmed 2026-08-11

### Spirits only is not a gap in coverage

Checked against the brief rather than assumed. `requirements.md` names three
beverage types exactly once, and prefaces it *"For reference"*:

> For reference, TTB requires specific information on alcohol beverage labels.
> The exact requirements vary by beverage type (beer, wine, distilled spirits)
> but common elements include: ...

That paragraph is background about TTB, not a feature list. The instruction is
further down, and it points at one worked example:

> Your app should handle labels containing information like the example below

followed by *Example Distilled Spirits Label Fields*. The only worked example
in the brief is spirits. The brief also states outright that *"a working core
application with clean code is preferred over ambitious but incomplete
features"*.

So spirits-complete is the intended shape, wine and malt stay declared but
unavailable with the reason shown in the UI, and no further corpus work is
needed for them. The independent requirements audit reached the same conclusion
unprompted. **Do not generate wine or malt labels.** Finding A5 stays open but
unreachable, and only becomes live if that decision is reversed.

### CORS_ORIGINS is a code default, not a Render setting

It is absent from the Render dashboard because it was never set there: the app
falls back to the default in `api/app/config.py`, which is
`http://localhost:5173`. That stale value is what made the session cookie
non-Secure in production, since the cookie flag used to be derived from it.

The cookie no longer depends on it, so what remains is tidiness: production
serves the UI and the API from one origin and needs no CORS at all. The fix
belongs in code — default to empty, and carry the localhost value in
`.env.example` where local development picks it up — rather than as another
variable to remember to set on a host.

## Session 5, 2026-08-11 — found while fixing the UI

Recorded here because both were live defects, not cosmetics.

| # | Status | Finding |
|---|---|---|
| S1 | **fixed** | **A phone photograph missed the headline requirement.** A 4116x5556 label took 9.3 s server-side against 2.7 s for the same label at 1372x1852. None of the difference was spent reading anything: the quality gate took 2,923 ms and geometric measurement 2,602 ms at a resolution neither uses, reaching the same verdict. Images above 2,000 px on the long edge are resampled once before the quality gate, and oversized JPEGs are decoded at a scaled size. Now p50 3,313 ms, p95 4,231 ms (n=10) |
| S2 | **fixed** | **The cropped-label check was never scale-invariant.** A fixed 6 px border band is 0.15% of a 4116 px frame and 1.1% of a 560 px one. Resampling turned that latent inconsistency into a live false FAIL: a border printed 10 px inside a large frame landed inside the band of the resampled image, and an intact label was rejected as running off the edge. The band is a fraction of the long edge now. Verified across all 95 curated and sample labels: no outcome moved |
| S3 | **fixed** | **The progress screen invented where the time went.** Three named stages advanced on fixed offsets from an old benchmark, so "checking each field against the application" was on screen whenever the wait ran long, whether or not anything was being checked. Two stages now, the first measured from real upload progress events |

## Standing note

`CORS_ORIGINS` on the deployed instance is still `http://localhost:5173`. The UI
is same-origin in production, so it is not needed there at all.
