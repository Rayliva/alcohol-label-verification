# Label Check — AI-powered alcohol label verification

Verifies alcohol beverage label artwork against the data declared in a TTB COLA
application. An agent supplies the label image and the declared values; within a
few seconds the tool returns a per-field verdict — **PASS**, **NEEDS REVIEW** or
**FAIL** — with the cropped region of the image that justifies each call. The
agent confirms or overrides. **The tool advises; the agent decides.**

**Live:** <https://alcohol-label-verification-3sn4.onrender.com>
· [health](https://alcohol-label-verification-3sn4.onrender.com/health)
· [API docs](https://alcohol-label-verification-3sn4.onrender.com/docs)

---

## Measured results

Everything below was measured against the deployed instance on **2026-08-09**,
with real Google Cloud Vision OCR and real Claude Haiku 4.5 extraction. Nothing
here is an estimate.

Reproduce any of it from `api/`, against a running instance with credentials
and the corpus generated:

```bash
uv run python -m app.bench.latency --base <url> --count 20    # the latency table
uv run python -m app.bench.latency --base <url> --accuracy    # end-to-end accuracy
uv run python -m app.bench.latency --base <url> --batch 200   # throughput
```

### Latency — the brief's most emphasised number

The stated bar is ~5 seconds, with a failure story attached: a prior vendor
pilot took 30–40 seconds and agents abandoned it.

| | Measured | Target |
|---|---|---|
| p50 | **2,430 ms** | — |
| **p95** | **4,525 ms** | < 5,000 ms |
| min / max | 1,991 / 4,954 ms | — |

n = 20 curated labels, sequential, warm instance.

Where the time goes, median per stage, server-side:

| Stage | Median |
|---|---|
| Decode | 20 ms |
| Quality gate | 24 ms |
| OCR (Cloud Vision) | 227 ms |
| **Field extraction (LLM)** | **1,664 ms** |
| Rule engine | 5 ms |
| Evidence crops | 89 ms |

The LLM call is 70% of the budget, which is why it never sees pixels — it reads
OCR text. A vision-model-first design would spend this three to five times over.

### Accuracy

Two numbers, because one of them would be misleading on its own.

| Measurement | Result | What it covers |
|---|---|---|
| **End to end** | **99.0%** — 291 of 294 field verdicts | Real OCR, real extraction, real verdicts across 49 curated labels |
| Rule engine alone | **100.0%** — 258 of 258 | OCR and extraction held perfect, so a wrong verdict is attributable to a rule |
| **False PASS on a government warning violation** | **0** | The error this product exists to prevent |

All three end-to-end misses are on tier-4 degraded-but-readable images — light
blur, underexposure, and a photograph at an angle — and all three are on the
warning's *geometric* checks, where the measurement degrades before the text
does. None is a missed violation: each is a compliant label flagged for review.

### Batch throughput

| | Measured |
|---|---|
| 200 labels | **69 seconds**, 0 errors |
| Throughput | 174 labels per minute at 8-way concurrency |
| Progress | determinate throughout: "47 of 200 checked" |

Peak season sends 200–300 applications at once. That run now takes about a
minute.

### What was not measured

- **Real photographs of real bottles.** The corpus is rendered, so its ground
  truth is exact; that is also its limitation. Foil, curved glass, script faces
  and embossing are not represented. The accuracy figures do not predict
  performance on them.
- **Wine and malt beverages.** The rule sets are declared but not populated
  (see Scope below), so no wine or malt label is scored.
- **Cold start.** The instance is on Render's always-on tier and is warmed at
  boot. A genuinely cold first request has not been timed.

---

## Running it

### The fast path — no credentials, no network

```bash
cd api
uv sync --extra server

# The corpus images are gitignored, so generate them first: the accuracy
# suite reads them, and five of the tests below fail without them.
uv run python ../corpus/generate.py --all       # 61 curated labels + fixtures
uv run python ../corpus/generate.py --batch 200 # the throughput fixture

uv run pytest -q                      # 274 tests, about 9 seconds
uv run pytest -q -m accuracy          # the corpus accuracy suite on its own
```

`OCR_ENGINE=fake` is the default. The entire stack, including the accuracy
suite, runs with no API keys and no outbound traffic. To skip the corpus
entirely, `uv run pytest -q -m "not accuracy"`.

### With real OCR and extraction

```bash
cp .env.example .env      # then fill in the two credentials
cd api
uv run uvicorn app.main:app --reload
```

| Variable | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | Field extraction |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Cloud Vision OCR (the whole service-account JSON, as a string) |
| `OCR_ENGINE` | `fake` (default), `cloud`, or `paddle` (not implemented) |

`/health` reports what warmed and what did not, and says which conditions are
known rather than actionable.

### The frontend

```bash
cd web
npm install
npm run dev        # http://localhost:5173, proxying /api to port 8000
npm run test       # 19 accessibility and behaviour tests, single pass
npm run test:watch # the same, in watch mode
npm run build
```

### Docker

```bash
docker compose up  # whole stack, OCR_ENGINE=fake, no keys, no network
```

---

## Approach

### The core decision: keep the vision model off the hot path

```
label image
  ├─ quality gate      readable? if not, stop with a specific reason
  ├─ OCR               text + bounding boxes            Cloud Vision  ~230 ms
  ├─ extraction        OCR text → structured fields     Claude Haiku  ~1,660 ms
  ├─ measurement       boxes + pixels → geometry
  ├─ rule engine       fields + geometry → verdicts     pure Python   ~5 ms
  └─ evidence crops    boxes → one PNG per field
```

Three properties follow. It is fast, because the model reads text rather than
pixels. Evidence crops are possible at all, because OCR returns bounding boxes.
And the compliance rules are pure functions over a data structure, so they are
unit-testable with no network — the rule engine's 166 tests run in 0.15
seconds.

### Three states, never two

A senior agent's example, verbatim from the brief: the label reads `STONE'S
THROW`, the application says `Stone's Throw`. Technically a mismatch; obviously
the same thing. A tool that calls that a failure gets ignored, so every field
resolves to PASS, NEEDS REVIEW or FAIL, and NEEDS REVIEW is where judgment
belongs.

A fourth outcome exists at the label level: **unreadable**. It is deliberately
not folded into FAIL. "We could not read this" is not "this label is
non-compliant" — the label may be perfectly compliant and badly photographed,
and conflating them would report compliant labels as violations and corrupt
every accuracy number above.

### The government warning gets six checks, not one

It is the only exact-match check in the product and the one agents describe
people trying hardest to game. Nothing in that module fuzzy-matches: whitespace
is normalised, because a line break on artwork is a layout artefact, and
everything else is compared character for character. Folding case would pass the
title-case violation the tool exists to catch.

`text_exact` · `caps` · `bold` · `proportion` · `contrast` · `field_of_vision`

Each is reported separately, so an agent sees *which* rule broke rather than one
amber badge on the most important field on the label.

### Beverage types are configuration, not code paths

Wine at 14% ABV or less may omit its alcohol content when the label says "table
wine" (27 CFR 4.36); a plain malt beverage needs none at all (27 CFR 7.63). An
engine that hardcodes the spirits rule — alcohol content always required — emits
false violations on two of the three categories. The engine reads field lists
from configuration; only spirits is populated.

### Every regulatory value was verified against a primary source

No CFR section, threshold or required text in this repository was written from
memory. Each was checked against Cornell LII on 2026-08-09, and the statutory
warning text was copied rather than retyped. A hallucinated threshold produces a
confident, authoritative, wrong answer whose wrongness is invisible — every
other bug in this system announces itself; that class does not.

---

## What the numbers are proxies for

27 CFR 16.22 states the warning's minimum type size in **millimetres**. That is
not derivable from an uncalibrated photograph, so three of the six warning
checks are proxies, calibrated against the corpus rather than asserted:

| Check | Proxy | Measured on the corpus |
|---|---|---|
| Bold | Stroke thickness of the prefix ÷ the text beside it | 1.35 compliant, 1.06 unbold |
| Proportion | Warning height ÷ median height of the other text | 0.525–0.610 compliant, 0.220 shrunken |
| Contrast | WCAG ratio inside the warning region | 18.6 compliant, 1.2 low-contrast |

Two of those three thresholds began as engineering guesses and both guesses were
wrong. Ink *density* does not detect bold — GOVERNMENT WARNING is uppercase and
the sentence beside it is not, so capitals moved the number as much as weight
did. And a compliant warning is legitimately smaller than the body copy, so an
80%-of-body-text threshold failed every clean label in the corpus. The corpus
found both.

**A geometric check with no measurement returns NEEDS REVIEW, never PASS.** A
check that silently passes when it did not run is a false PASS, and false PASSes
are the error class this product is scored on.

---

## Scope and trade-offs

### Shipped

Single-label review · six-check government warning · fuzzy text matching with
abbreviation and corporate-suffix handling · numeric ABV and net-contents
matching with unit conversion · evidence crops · agent override with notes ·
batch upload with pre-flight, live progress and CSV export · specific reasons
for unreadable images.

### Deliberately not built

| | Why |
|---|---|
| **Wine and malt rule content** | Spirits is the type the brief exemplifies and the only one with no ABV conditional. The engine reads all three from configuration and the UI disables the other two *with the reason attached*. Shipping spirits complete beats three types half-finished |
| **Authentication** | Not requested, and real auth means storing credentials, which contradicts storing nothing. An optional "your name or initials" attributes overrides within a session |
| **Persistence** | The brief says not to store anything sensitive. Nothing is stored — a restart loses in-flight batch jobs, and the API says so when asked about one |
| **Absolute millimetre type size** | Physically underivable from an uncalibrated image. The proportional proxy ships instead, documented as a proxy |
| **PDF upload** | The design handoff lists it; the brief does not. A PDF is rejected by name — "This is a PDF… export the artwork as a JPG or PNG" — rather than failing generically |
| **Image preprocessing (deskew, glare removal)** | The quality gate detects and reports these; correcting them is Phase 4 |
| **Vision-model escalation** | Would ship only if the corpus showed OCR failing on labels a human can read. It does not, so it has not |

### Known limitations

- **The corpus is rendered.** Ground truth is exact, which is why the accuracy
  numbers mean anything — and it does not stress OCR against foil, curved glass,
  or script faces. Real photographs belong in the corpus as an unscored smoke
  set; they are not there yet.
- **Prompt caching does not engage.** The system prompt is below Haiku 4.5's
  1,024-token minimum cacheable prefix. Padding the prompt to reach the
  threshold would be gaming a number, so it is reported on `/health` and left
  alone. It costs a little per request and changes no behaviour.
- **Glare on pure-white artwork is undetectable** by the luminance check, since
  a reflection has no headroom above white paper. Such an image falls through to
  the OCR checks and is reported unreadable for a different reason.
- **The frontend bundle is committed** under `api/app/static`, because Render's
  build context is `api/` and the container cannot reach `web/`. A UI change
  needs `npm run build` and a commit. The production shape is a separate Vercel
  deployment, per the tech spec.
- **`field_of_vision` reads panels from image geometry.** A front-and-back
  photograph works; a single photograph of a wrap-around label does not tell us
  what is on the other side.

---

## Production considerations

Not built, and named rather than left implied:

- **Authentication and audit.** Agency SSO or PIV, role separation, and an
  append-only record of who overrode what. The override model already keeps the
  tool's verdict alongside the agent's decision, which is the shape an audit
  needs.
- **The firewall.** TTB blocks outbound traffic to many domains, which conflicts
  with a hosted OCR provider. `OcrEngine` is an interface with `cloud`, `fake`
  and a documented `paddle` adapter; the on-prem answer is a configuration
  change, not a rewrite. The adapter itself is not implemented.
- **Scale.** One process, an in-memory job store, and a thread pool. The store
  sits behind a small interface so it can become Redis; 150,000 applications a
  year is about 600 a working day, which this handles, but not with one process
  and no queue.
- **Retention.** Nothing is stored today. Anything that changes that inherits
  the PII and retention questions the brief raises.

---

## Tools and stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 | The OCR and image ecosystem is first-class here and awkward elsewhere |
| OCR | Google Cloud Vision, behind a `Protocol` | Fast, strong on stylised type, returns bounding boxes — which is what makes evidence crops possible |
| Extraction | Claude Haiku 4.5, structured outputs, thinking disabled, temperature 0 | Benchmarked against Opus 5 and Sonnet 5 during the spike. Structured outputs remove the parse-and-retry loop; temperature 0 because the same label must get the same verdict twice |
| Rules | Pure Python, no dependencies | Unit-testable with no network. The whole engine runs in 5 ms |
| Frontend | React 19, Vite, TypeScript, hand-written CSS tokens | The design specifies exact values throughout, and each is an accessibility decision with a reason |
| Tests | pytest, Vitest, Testing Library | 274 backend, 19 frontend |
| Hosting | Render, always-on tier, from `api/Dockerfile` | Cold starts sabotage the evaluator's first click |

---

## Repository

```
requirements.md          the brief, verbatim — never edited
docs/
  PRD.md                 derived requirements, scope, test corpus
  tech-spec.md           stack and architecture
  ui-spec.md             screens, data shape, design resolutions
  build-loop.md          current state and the build procedure
  specs/                 rule-engine, pipeline, batch
docker-compose.yml       one command, fixtures, no keys, no network
api/
  Dockerfile             multi-stage; Render deploys from this
  app/rules/             the compliance engine — pure, no I/O
  app/ocr/               OcrEngine protocol, Cloud Vision, fixtures
  app/extraction/        the LLM client, prompt and structured-output schema
  app/pipeline/          quality gate, measurement, crops, orchestration
  app/batch/             manifest parsing, job store, worker pool
  app/api/               HTTP layer
  app/bench/             the measurement harness behind every number above
  app/static/            the built frontend, served from the same origin
corpus/
  render.py              draws a label and records where every line landed
  generate.py            61 curated labels, 200-label batch, malformed manifests
  fixtures/              expected verdicts and ground-truth OCR
web/                     React frontend
prompts/                 the prompts this project was bootstrapped from
```

`.claude/rules/` holds the constraints this build was written under — verify
regulations against source, measure rather than claim, no generic failures, the
accessibility bar. They are worth reading if you want to know why the code looks
the way it does.
