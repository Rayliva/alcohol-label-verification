# Alcohol Label Verification

Verifies alcohol beverage label artwork against the data declared in a TTB COLA
application. An agent supplies the label image and the declared values; within a
few seconds the tool returns a per-field verdict, **PASS**, **NEEDS REVIEW** or
**FAIL**, with the cropped region of the image that justifies each call. The
agent confirms or overrides. **The tool advises; the agent decides.**

**Live:** <https://alcohol-label-verification-3sn4.onrender.com>
· [health](https://alcohol-label-verification-3sn4.onrender.com/health)
· [API docs](https://alcohol-label-verification-3sn4.onrender.com/docs)

## Known trade-offs, up front

The decisions that most shaped this prototype. Each is expanded in
[Scope and trade-offs](#scope-and-trade-offs), [Approach](#approach), and
[Known limitations](#known-limitations).

- **Spirits only.** The engine reads wine and malt rules from the same
  configuration, but their rule content is not shipped: one type complete
  beats three half-finished. The UI says so rather than hiding it.
- **The vision model is off the hot path.** OCR plus text-only extraction
  meets the 5-second budget; a vision call per label would not. The cost: no
  glare or skew correction. An unreadable photo is refused with the specific
  reason instead of guessed at.
- **Nothing is persisted.** The review queue lives in memory, seeded at boot
  from results recorded at build time; a restart loses uploads and decisions.
- **Warning type size is a proportional proxy.** Absolute millimetres are not
  derivable from an uncalibrated photo, so size relative to surrounding text
  stands in, documented as a proxy.
- **Sign-in is a demonstration gate, not an identity system.** One shared
  credential from the environment keeps a public URL off the open web; no
  accounts, no stored credentials, no coordination between concurrent agents.
- **Seeded queue verdicts are recorded, not recomputed.** They came from the
  real pipeline via a checked-in script; the queue renders instantly and
  identically on every boot, at the cost of being fixtures.
- **Every published number is a measurement** with a date and corpus, the
  unflattering ones included. What was not measured is listed as such.

---

## Measured results

Measured against the deployed instance on **2026-08-11**, with real Cloud
Vision OCR and real Claude Haiku 4.5 extraction. Reproduce from `api/` with
the corpus generated; the first three commands sign in, so
`AGENT_USERNAME`/`AGENT_PASSWORD` must be set for the target instance:

```bash
uv run python -m app.bench.latency --base <url> --count 20    # latency
uv run python -m app.bench.latency --base <url> --accuracy    # end-to-end accuracy
uv run python -m app.bench.latency --base <url> --batch 200   # throughput
uv run pytest -q -m accuracy                                  # the rule engine alone
```

### Latency

The brief's bar is ~5 seconds; a prior vendor pilot took 30–40 and was
abandoned.

| | Measured | Target |
|---|---|---|
| p50 | **2,203 ms** | |
| **p95** | **2,889 ms** | < 5,000 ms |
| min / max | 1,997 / 2,894 ms | |

n = 20 curated labels, sequential, warm instance. Median per stage,
server-side: decode
18 ms, quality gate 130 ms, OCR 218 ms, **field extraction 1,436 ms**, rules
137 ms, crops 10 ms. The LLM call is 65% of the budget, which is why it reads
OCR text and never pixels.

**A phone photograph is a different measurement.** Curated labels are
1,000–2,000 px on the long edge; a phone photo is four times that, and until
2026-08-11 it missed the headline requirement:

| 4116 x 5556 px, 1.1 MB | Before | After |
|---|---|---|
| Server, p50 | 9,305 ms | 3,313 ms |
| Server, p95 | not measured, n=2 | 4,231 ms |
| End to end from a laptop, p95 | | 4,834 ms |

n = 10 after, n = 2 before, sequential, same instance and same image. The
lost seconds were spent measuring quality and geometry at a resolution
neither uses. Anything above 2,000 px is now resampled once, before the
quality gate, and 2,000 px is the top of the range every threshold was
calibrated against.

### Accuracy

| Measurement | Result | What it covers |
|---|---|---|
| **End to end** | **99.0%**, 291 of 294 field verdicts | Real OCR, real extraction, 49 curated labels |
| Rule engine alone | **100.0%**, 258 of 258 | OCR and extraction held perfect, so a miss is attributable to a rule |
| **Independently authored set** | **22 of 31** | Ground truth this project did not write |
| **False PASS on a warning violation** | **0** | The error this product exists to prevent |

All three end-to-end misses are on the warning's *geometric* checks, and all
three land on **needs review** rather than a wrong verdict: two compliant
labels flagged for a human (`t4-blur-light`, `t4-skew`) and one real violation
under-called but still flagged (`t2-warning-too-small`). Zero false PASS
holds, and no compliant label is rejected.

Behind `t4-blur-light`: softness inverts the relative stroke-weight ratio
(1.35 compliant, 1.06 genuinely un-bold, 0.90 compliant-but-soft), so below
focus 8.0 the fragile geometric measurements are withheld and the check asks
for a human. A withheld measurement can only become "look at this", never a
pass. These proxy checks remain the weakest part of the build.

**Against ground truth we did not write:** a second, externally authored set
of 31 labels (`samples/`) agrees with 22. Of the nine disagreements, three are
a deliberate difference (`STONE'S THROW` vs `Stone's Throw`: this tool passes
what that set surfaces), three are this tool refusing to guess at warning text
on blurred labels, and three are the geometric checks above, all flagged for
review rather than decided wrongly.

### Batch

| | Measured |
|---|---|
| 200 labels | **81 seconds**, 0 errors |
| Throughput | 147.5 labels per minute at 8-way concurrency |
| Progress | determinate throughout: "47 of 200 checked" |

**Ready-made batch tests:** `api/app/samples/` (31 labels) and
`samples/batch/` (25 labels) each contain a `batch-manifest.csv` naming
exactly the images beside it. Select a folder's JPGs plus the CSV in the same
folder; preflight matches all with no skips. Rows name files by exact
filename, so a CSV paired with any other folder reports every row unmatched.
A test keeps each shipped CSV matched to its own folder.

### What was not measured

- **Real photographs of real bottles**: the corpus is rendered; foil, curved
  glass, script faces and embossing are not represented.
- **Wine and malt beverages**: rule sets declared but not populated.
- **Cold start**: the instance is always-on and warmed at boot.
- **The upload leg**: latency figures are server-side or from one laptop; the
  progress screen reports the agent's own upload from real events.

---

## Running it

### The test suite: no credentials, no network

```bash
cd api
uv sync --extra server

# The corpus images are gitignored; the accuracy suite and most of the
# integration suite read them and fail without them.
uv run python ../corpus/generate.py --all       # 61 curated labels + fixtures
uv run python ../corpus/generate.py --batch 200 # the throughput fixture

uv run pytest -q                      # 439 tests as of 2026-08-12
uv run pytest -q -m accuracy          # the corpus accuracy suite alone
```

The whole suite, accuracy included, needs no credentials and makes no outbound
calls: `tests/conftest.py` blanks the credentials and both external boundaries
are injected as fakes.

### With real OCR and extraction

```bash
cp .env.example .env      # fill in the four values the table marks
cd api
uv run uvicorn app.main:app --reload
```

| Variable | Used by | Required to boot |
|---|---|---|
| `AGENT_USERNAME` | Sign-in. One shared credential, delivered out of band | **Yes** |
| `AGENT_PASSWORD` | Sign-in | **Yes** |
| `ANTHROPIC_API_KEY` | Field extraction | No, but every check fails without it |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Cloud Vision OCR (the service-account JSON, as a string) | No, unless `OCR_ENGINE=cloud` |
| `SESSION_SECRET` | Signs the session cookie; unset means everyone signs in again after a restart | No |
| `OCR_ENGINE` | `fake` (default), `cloud`, or `paddle` (not implemented) | No |

The app refuses to boot without the agent credentials rather than serving the
queue to anyone who finds the URL. `/health` reports what warmed and what did
not.

### The frontend

```bash
cd web
npm install
npm run dev        # http://localhost:5173, proxying /api to port 8000
npm run test       # 31 accessibility and behaviour tests
npm run build
```

One deliberate redundancy in the results UI: the verdict is stated in words,
in a per-field counts line, and visually. The glyph is decorative to a screen
reader, so the words carry everything.

### Docker

```bash
AGENT_USERNAME=agent AGENT_PASSWORD=choose-one ANTHROPIC_API_KEY=sk-ant-... docker compose up
```

API and UI on <http://localhost:8000> with `OCR_ENGINE=fake`: no Cloud Vision
account needed. Two caveats: an Anthropic key is still required (extraction
has no fixture path), and `fake` OCR returns one built-in sample label
regardless of what is uploaded, so it proves the stack is wired, not the
product. For the product, use `OCR_ENGINE=cloud` or the deployed instance.

---

## Approach

### The core decision: keep the vision model off the hot path

```
label image
  ├─ decode            upright RGB, resampled to 2,000 px if larger    ~18 ms
  ├─ quality gate      readable? if not, stop with a specific reason   ~130 ms
  ├─ OCR               text + bounding boxes            Cloud Vision   ~218 ms
  ├─ extraction        OCR text -> structured fields    Claude Haiku   ~1,436 ms
  ├─ measurement       boxes + pixels -> geometry
  ├─ rule engine       fields + geometry -> verdicts    pure Python    ~137 ms
  └─ evidence crops    boxes -> one PNG per field                      ~10 ms
```

Three properties follow: it is fast, because the model reads text rather than
pixels; evidence crops are possible, because OCR returns bounding boxes; and
the compliance rules are pure functions, unit-testable with no network (212
rule-engine tests, no credentials, no fixtures on disk).

### OCR modes, and why the seam exists

`OCR_ENGINE` selects a mode behind a single `Protocol` (`api/app/ocr/base.py`);
each returns full text plus per-block bounding boxes.

| Mode | What it is | Credentials | Used for |
|---|---|---|---|
| `cloud` | Google Cloud Vision | Service-account JSON | Production, and every published measurement |
| `fake` | One built-in sample label, returned for every image | None | Booting the stack without a Cloud Vision account |
| `paddle` | Local PaddleOCR | None | **Not implemented.** The documented on-prem path |

The seam exists because TTB's network blocks outbound traffic to many domains
(their IT admin, in the brief): behind an interface, on-prem OCR is a
configuration change, not a rewrite. It also lets tests hold OCR still with a
test-only engine replaying the corpus renderer's own bounding boxes, which is
what makes a wrong verdict attributable to a rule rather than a misread
character. Extraction has no such seam, a documented gap: a running server
always calls Anthropic.

### Three states, never two

The brief's own example: the label reads `STONE'S THROW`, the application says
`Stone's Throw`. Technically a mismatch, obviously the same thing. A tool that
calls that a failure gets ignored, so every field resolves to PASS, NEEDS
REVIEW or FAIL, and NEEDS REVIEW is where judgment belongs. A fourth outcome,
**unreadable**, exists at the label level and is deliberately not folded into
FAIL: "we could not read this" is not "this label is non-compliant".

### The government warning gets six checks, not one

`text_exact` · `caps` · `bold` · `proportion` · `contrast` · `field_of_vision`

It is the only exact-match check in the product. Whitespace is normalised
(a line break on artwork is a layout artefact); everything else is compared
character for character, because folding case would pass the title-case
violation the tool exists to catch. Each check is reported separately, so an
agent sees which rule broke.

### Beverage types are configuration, not code paths

Wine at 14% ABV or less may omit alcohol content when labelled "table wine"
(27 CFR 4.36); a plain malt beverage needs none (27 CFR 7.63). Hardcoding the
spirits rule would emit false violations on both, so the engine reads field
lists from configuration; only spirits is populated.

### Every regulatory value was verified against a primary source

No CFR section, threshold or required text here was written from memory. Each
was checked against Cornell LII on 2026-08-09, and the statutory warning text
was copied, never retyped. A hallucinated threshold produces a confident,
authoritative, wrong answer whose wrongness is invisible.

### What the numbers are proxies for

27 CFR 16.22 states the warning's minimum type size in millimetres, which is
not derivable from an uncalibrated photograph. Three of the six warning checks
are proxies, calibrated against the corpus rather than asserted:

| Check | Proxy | Measured on the corpus |
|---|---|---|
| Bold | Stroke thickness of the prefix ÷ the text beside it | 1.35 compliant, 1.06 unbold |
| Proportion | Warning height ÷ median height of other text | 0.525–0.610 compliant, 0.220 shrunken |
| Contrast | WCAG ratio inside the warning region | 18.6 compliant, 1.2 low-contrast |

Two of the three thresholds began as engineering guesses; the corpus proved
both wrong and supplied the values above. **A geometric check with no
measurement returns NEEDS REVIEW, never PASS**: a check that silently passes
when it did not run is a false PASS, the error class this product exists to
prevent.

---

## Scope and trade-offs

**On the TTB seal.** The sign-in screen and masthead carry the Bureau's seal
(from ttb.gov) so the screens read as what they are meant to sit inside.
**This is a prototype written against a take-home brief. It is not a TTB
product, is not affiliated with the Bureau, and no verdict it produces is an
official determination.**

### Shipped

Single-label review · six-check government warning · fuzzy text matching with
abbreviation and corporate-suffix handling · numeric ABV and net-contents
matching with unit conversion · evidence crops · batch upload with pre-flight,
live progress and CSV export · specific reasons for unreadable images · a
review queue with search, filters, and an opt-in "Start reviewing" run where
each decision opens the next undecided application · uploads and batch results
join the queue, searchable by declared application ID, with the measured wait
("Checked in 4.2 seconds") and Approve/Reject on the result.

### Deliberately not built

| | Why |
|---|---|
| **Wine and malt rule content** | Spirits is the type the brief exemplifies; the engine reads all three from configuration and the UI names the gap with the reason attached |
| **Real authentication** | One shared credential in a signed HttpOnly cookie keeps the public URL gated without storing credentials. No accounts, no reset, no roles; none of which the brief asks for |
| **Persistence** | The brief says not to store anything sensitive; nothing is stored. A restart returns the queue to its seeded state and loses uploads, decisions, and in-flight batch jobs, and the API says so |
| **Absolute millimetre type size** | Physically underivable from an uncalibrated image; the proportional proxy ships, documented as a proxy |
| **PDF upload** | Not in the brief. A PDF is rejected by name rather than failing generically |
| **Image preprocessing (deskew, glare removal)** | The quality gate detects and reports these; correcting them is future work |
| **Vision-model escalation** | Would ship only if the corpus showed OCR failing on labels a human can read; it does not |

### Known limitations

- **A label running out of frame is refused** even when the visible fields are
  readable: the missing strip is exactly where a mandatory element could hide.
  The agent is told which edge is cut.
- **A frame that is blurred, underexposed *and* noisy can be misreported**:
  the cause named may be wrong, though the image is still refused. Measured in
  `docs/specs/pipeline.md` 2.1.
- **The corpus is rendered.** Exact ground truth, no stress against foil,
  curved glass, or script faces.
- **Prompt caching does not engage**: the system prompt is below the model's
  minimum cacheable prefix. Padding it to reach the threshold would be gaming
  a number, so `/health` reports it and it is left alone.
- **Glare on pure-white artwork is undetectable** by the luminance check; such
  an image is refused by the OCR checks for a different stated reason.
- **The credential-free path boots the stack but cannot demonstrate it**:
  `fake` OCR ignores the uploaded image and extraction has no fixture path.
  Tests are unaffected; they inject fakes at both boundaries.
- **The frontend bundle is committed** under `api/app/static` because Render's
  build context cannot reach `web/`. A UI change needs `npm run build` and a
  commit.
- **`field_of_vision` reads panels from image geometry**: a single photo of a
  wrap-around label cannot say what is on the other side.
- **Photographs above 2,000 px are resampled before anything reads them.** No
  verdict moved on any of the 95 curated and sample labels; very small print
  on a very large photo is the untested case.
- **The sign-in gate has prototype-grade edges**: no login throttle, and
  signing out does not revoke the signed session token before its 12-hour
  expiry (rotating `SESSION_SECRET` is the kill switch). Both are the cost of
  storing no credential state.
- **Text printed on the artwork reaches the extraction model.** The schema and
  the deterministic rule engine bound what that can steer, and the evidence
  crops show the real pixels, but the channel exists; a compliance deployment
  would want it adversarially tested.
- **A batch's full reports are held twice in memory** (job store and review
  queue) for the life of the process: roughly twice the report size per run.
- **Two image checks are resolution-sensitive by construction**; the border
  band is proportional for exactly this reason, and focus is measured on what
  the OCR engine will read.

### Production considerations

Not built, and named rather than left implied: agency SSO/PIV with an
append-only audit record (the override model already keeps the tool's verdict
beside the agent's decision, which is the shape an audit needs); the on-prem
OCR adapter for TTB's firewall; a real job store and horizontal scale
(150,000 applications a year is about 600 a working day); and retention
policy, which nothing inherits today because nothing is stored.

---

## Tools and stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 | The OCR and image ecosystem is first-class here |
| OCR | Google Cloud Vision, behind a `Protocol` | Fast, strong on stylised type, returns the bounding boxes that make evidence crops possible |
| Extraction | Claude Haiku 4.5, structured outputs, thinking disabled, temperature 0 | Benchmarked against Opus 5 and Sonnet 5 during the spike; the same label must get the same verdict twice |
| Rules | Pure Python, no dependencies | Unit-testable with no network; the whole engine runs in 5 ms |
| Frontend | React 19, Vite, TypeScript, hand-written CSS tokens | Each value is an accessibility decision with a reason |
| Tests | pytest, Vitest, Testing Library | 439 backend, 31 frontend (2026-08-12) |
| Hosting | Render, always-on tier, from `api/Dockerfile` | A spun-down instance would miss the 5-second budget on its first request |

## Repository

```
requirements.md          the brief, verbatim. Never edited
docs/
  PRD.md                 derived requirements, scope, test corpus
  tech-spec.md           stack and architecture
  ui-spec.md             screens, data shape, design resolutions
  build-loop.md          current state and the build procedure
  audit-findings.md      every defect found by audit, triaged, with status
  specs/                 rule-engine, pipeline, batch, review-queue
docker-compose.yml       one command; fixture OCR, still needs an Anthropic key
api/
  app/rules/             the compliance engine, pure, no I/O
  app/ocr/               OcrEngine protocol, Cloud Vision, fixtures
  app/extraction/        the LLM client, prompt and structured-output schema
  app/pipeline/          quality gate, measurement, crops, orchestration
  app/batch/             manifest parsing, job store, worker pool
  app/review/            the in-memory review queue
  app/api/               HTTP layer
  app/bench/             the measurement harness behind every number above
  app/static/            the built frontend, served from the same origin
corpus/                  label renderer, 61 curated labels, fixtures
samples/                 externally authored labels with independent ground truth
web/                     React frontend
```

`.claude/rules/` holds the constraints this build was written under: verify
regulations against source, measure rather than claim, no generic failures,
the accessibility bar.
