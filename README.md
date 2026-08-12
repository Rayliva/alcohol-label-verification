# Alcohol Label Verification

Verifies alcohol beverage label artwork against the data declared in a TTB COLA
application. An agent supplies the label image and the declared values; within a
few seconds the tool returns a per-field verdict, **PASS**, **NEEDS REVIEW** or
**FAIL**, with the cropped region of the image that justifies each call. The
agent confirms or overrides. **The tool advises; the agent decides.**

**Live:** <https://alcohol-label-verification-3sn4.onrender.com>
· [health](https://alcohol-label-verification-3sn4.onrender.com/health)
· [API docs](https://alcohol-label-verification-3sn4.onrender.com/docs)

---

## Measured results

Everything below was measured against the deployed instance on **2026-08-11**,
with real Google Cloud Vision OCR and real Claude Haiku 4.5 extraction. Nothing
here is an estimate. Re-measured that day because the rule engine changed four
times: published numbers that describe an older build are not measurements.

Reproduce any of it from `api/`, against a running instance with credentials
and the corpus generated:

```bash
uv run python -m app.bench.latency --base <url> --count 20    # the latency table
uv run python -m app.bench.latency --base <url> --accuracy    # end-to-end accuracy
uv run python -m app.bench.latency --base <url> --batch 200   # throughput
uv run pytest -q -m accuracy                                  # the rule engine alone
```

The first three sign in, so `AGENT_USERNAME` and `AGENT_PASSWORD` must be set
for the instance being measured.

### Latency: the brief's most emphasised number

The stated bar is ~5 seconds, with a failure story attached: a prior vendor
pilot took 30–40 seconds and agents abandoned it.

| | Measured | Target |
|---|---|---|
| p50 | **2,203 ms** | |
| **p95** | **2,889 ms** | < 5,000 ms |
| min / max | 1,997 / 2,894 ms | |

n = 20 curated labels, sequential, warm instance, 2026-08-11.

Where the time goes, median per stage, server-side:

| Stage | Median |
|---|---|
| Decode | 18 ms |
| Quality gate | 130 ms |
| OCR (Cloud Vision) | 218 ms |
| **Field extraction (LLM)** | **1,436 ms** |
| Rule engine | 137 ms |
| Evidence crops | 10 ms |

The LLM call is 65% of the budget, which is why it never sees pixels. It reads
OCR text. A vision-model-first design would spend this three to five times over.

The quality gate went from 24 ms to 130 ms when focus and contrast were made
independent of exposure, which costs a median filter and two histogram passes.
A tenth of a second against a five-second budget, to stop reporting
underexposed labels as blurry ones and compliant labels as warning violations.

#### A phone photograph, which is not the same measurement

Every number above is a curated label: 1,000 to 2,000 px on the long edge,
which is what an artwork export looks like. A photograph taken on a phone is
four times that in each direction, and until 2026-08-11 the tool handled it
badly enough to miss its headline requirement.

| 4116 x 5556 px, 1.1 MB | Before | After |
|---|---|---|
| Server, p50 | 9,305 ms | 3,313 ms |
| Server, p95 | not measured, n=2 | 4,231 ms |
| End to end from a laptop, p95 | | 4,834 ms |

n = 10 after, n = 2 before, sequential, same instance and same image.

None of that time was ever spent reading anything. The quality gate took
2,923 ms and geometric measurement 2,602 ms, both at a resolution neither can
use, and both arrived at the verdict they arrive at now. Anything above 2,000
px on its long edge is resampled once, before the quality gate, and every
stage after it sees the same pixels, OCR included. Oversized JPEGs are decoded
straight to a scaled size rather than decoded whole and then shrunk.

2,000 px is the top of the range the thresholds were calibrated against, not a
number above it: the largest curated label is 2,000 px and the largest sample
1,932, so nothing any threshold was measured on is resampled, and anything
that is resampled lands inside that range. Making that change also required
making the cropped-label check scale-invariant, because a fixed 6 px border
band asks a different question of a 4116 px frame than of a 560 px one. See
Limitations.

### Accuracy

Two numbers, because one of them would be misleading on its own.

| Measurement | Result | What it covers |
|---|---|---|
| **End to end** | **99.0%**, 291 of 294 field verdicts | Real OCR, real extraction, real verdicts across 49 curated labels |
| Rule engine alone | **100.0%**, 258 of 258 | OCR and extraction held perfect, so a wrong verdict is attributable to a rule |
| **Independently authored set** | **22 of 31** | Ground truth this project did not write. See below |
| **False PASS on a government warning violation** | **0** | The error this product exists to prevent |

All three end-to-end misses are on the warning's *geometric* checks, where the
measurement degrades before the text does. All three now land on **needs
review**, meaning a person is asked to look, rather than on a wrong verdict:

| Label | Expected | Got | |
|---|---|---|---|
| `t4-blur-light` | pass | needs review | Too soft to measure stroke weight, so it is not measured. Until 2026-08-11 this was a **false FAIL**. See below |
| `t4-skew` | pass | needs review | Compliant label flagged for a human. The intended behaviour when a measurement is uncertain |
| `t2-warning-too-small` | fail | needs review | A real violation under-called. Flagged rather than failed, so it still reaches an agent |

Zero false PASS holds, and there is no false FAIL: nothing non-compliant was
waved through, and no compliant label was rejected.

**Why `t4-blur-light` used to fail.** Bold is measured as the stroke weight of
`GOVERNMENT WARNING` relative to the text around it. Softening the image does
not merely degrade that ratio, it inverts it: measured on this corpus a
compliant label reads 1.35, a genuinely un-bold one 1.06, and a compliant one
photographed slightly soft **0.90**, below the real defect. A verdict drawn
from that describes the photograph, not the label.

The mechanism is not settled. Convergence toward 1.0 would be unsurprising;
crossing *below* the un-bold case is not, and the likeliest explanation is that
blur bridges the tight gaps between lowercase letters in the body text, merging
them into longer runs and inflating the denominator, while widely-set capitals
in the heading bridge far less. That has not been measured carefully enough to
publish as fact, which is why the threshold below rests on the three readings
above rather than on a theory of why they move.

Readable and measurable are now separate bars. Focus separates them cleanly:
the soft label reads 5.19 where every other compliant label sits at 12.11–15.62
and all three genuine warning defects at 13.51 to 15.43, so below 8.0 the fragile
measurements are simply not reported, and the check asks for a human instead.
A withheld measurement can only become "look at this", never a pass, so this
cannot hide a violation; it can only stop inventing one.

Text height is left alone: it survives softness where stroke weight does not.

**These checks remain the weakest part of the build.** They are proxies, relative
stroke weight for boldness and proportional height for type size, and
both degrade before the text does. The remaining under-call above
(`t2-warning-too-small`) is one of them.

### Against ground truth we did not write

The figures above are measured on a corpus this project generated, which is a
real limitation however carefully it was built. A second set of 31 labels with
independent ground truth (`samples/`) agrees with **22**. The nine
disagreements are worth more than the number:

- **Three are a deliberate difference.** `STONE'S THROW` against `Stone's Throw`,
  `750ML` against `750 mL`, `47%` against `47.0%`. This tool passes them, that
  set wants them surfaced for review. Dave Morrison's interview is the argument
  for passing them; caution is the argument for surfacing them.
- **Three are this tool refusing to guess.** Blurred labels where the warning
  text cannot be read. That set expects a verdict; this tool asks for a better
  photograph, because guessing at warning text is the one thing it must not do.
- **Three are genuinely open**, the same geometric checks named above. All
  three are flagged for review rather than decided wrongly: two compliant
  labels this tool will not commit to (`026_dim` at focus 6.23, below the
  measurement bar, and `027_curved` whose bold reading lands in the review
  band), and one real violation under-called (`016_warning_tiny`), which still
  reaches an agent.

That set also found two real defects on arrival: a country of origin declared
as `PRODUCT OF ENGLAND` failing against a label reading `ENGLAND`, and an
imported label naming no country passing clean.

### Batch throughput

| | Measured |
|---|---|
| 200 labels | **81 seconds**, 0 errors |
| Throughput | 147.5 labels per minute at 8-way concurrency |
| Progress | determinate throughout: "47 of 200 checked" |

Peak season sends 200–300 applications at once. Two hundred takes 81 seconds;
three hundred would take a little over two minutes.

### What was not measured

- **Real photographs of real bottles.** The corpus is rendered, so its ground
  truth is exact; that is also its limitation. Foil, curved glass, script faces
  and embossing are not represented. The accuracy figures do not predict
  performance on them.
- **Wine and malt beverages.** The rule sets are declared but not populated
  (see Scope below), so no wine or malt label is scored.
- **Cold start.** The instance is on Render's always-on tier and is warmed at
  boot. A genuinely cold first request has not been timed.
- **The upload leg.** Every latency figure is server-side or measured from one
  laptop on one connection. What an agent waits for includes sending the image,
  which depends on their upload bandwidth and is not something this project can
  measure for them. The progress screen reports that half from real upload
  events rather than estimating it.

---

## Running it

### The test suite: no credentials, no network

```bash
cd api
uv sync --extra server

# The corpus images are gitignored, so generate them first: the accuracy
# suite and most of the integration suite read them, and 81 of the 285
# tests below fail without them.
uv run python ../corpus/generate.py --all       # 61 curated labels + fixtures
uv run python ../corpus/generate.py --batch 200 # the throughput fixture

uv run pytest -q                      # 285 tests
uv run pytest -q -m accuracy          # the corpus accuracy suite on its own
```

**The test suite needs no credentials and makes no outbound calls**, and that
includes the accuracy suite. `tests/conftest.py` blanks both credentials for
every test, and the two external boundaries are injected as fakes. To skip the
corpus entirely, `uv run pytest -q -m "not accuracy"`.

**A running server is a different matter.** `OCR_ENGINE=fake` removes the need
for Cloud Vision credentials, but field extraction has no equivalent seam: it
always calls the Anthropic API, so a server started without
`ANTHROPIC_API_KEY` will boot, serve the UI, and then fail on every check. See
[OCR modes](#ocr-modes-and-why-the-seam-exists) below.

### With real OCR and extraction

```bash
cp .env.example .env      # then fill in the two credentials
cd api
uv run uvicorn app.main:app --reload
```

| Variable | Used by | Required to boot |
|---|---|---|
| `AGENT_USERNAME` | Sign-in. One shared credential, delivered out of band | **Yes** |
| `AGENT_PASSWORD` | Sign-in | **Yes** |
| `ANTHROPIC_API_KEY` | Field extraction | No, but every check fails without it |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Cloud Vision OCR (the whole service-account JSON, as a string) | No, unless `OCR_ENGINE=cloud` |
| `SESSION_SECRET` | Signs the session cookie. Unset means a new key each boot, so everyone signs in again after a restart | No |
| `OCR_ENGINE` | `fake` (default), `cloud`, or `paddle` (not implemented) | No |

The app refuses to start without the agent credentials rather than serving the
review queue to anyone who finds the URL. `.env.example` lists every variable.

`/health` reports what warmed and what did not, and says which conditions are
known rather than actionable.

### The frontend

```bash
cd web
npm install
npm run dev        # http://localhost:5173, proxying /api to port 8000
npm run test       # 17 accessibility and behaviour tests, single pass
npm run test:watch # the same, in watch mode
npm run build
```

### Docker

```bash
AGENT_USERNAME=agent AGENT_PASSWORD=choose-one ANTHROPIC_API_KEY=sk-ant-... docker compose up
```

Runs the API and the UI on <http://localhost:8000> with `OCR_ENGINE=fake`, so
no Cloud Vision credentials are needed and no OCR traffic leaves the machine.
The agent credentials are yours to choose here; the app asserts their presence
at startup and will not boot without them. Sign in with them at the UI.

Two things this does **not** give you, both named under
[Limitations](#known-limitations) rather than left to be discovered:

- **An Anthropic key is still required.** Extraction has no fixture path, so
  without one the container starts, `/health` carries a note saying so, and a check fails as
  soon as a readable image reaches the extraction step.
- **`fake` ignores the image you upload.** It returns one built-in sample label
  every time, so a check run this way reports on that sample and not on your
  artwork. It proves the stack is wired together; it does not demonstrate the
  product. For that, set `OCR_ENGINE=cloud` with Cloud Vision credentials, or
  use the deployed instance.

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

Medians from the same run as the latency table above. Measurement and the rule
engine share a stage timer; the rules themselves are a few milliseconds of it.

Three properties follow. It is fast, because the model reads text rather than
pixels. Evidence crops are possible at all, because OCR returns bounding boxes.
And the compliance rules are pure functions over a data structure, so they are
unit-testable with no network. The rule engine's 212 tests need no
credentials and no fixtures on disk.

### OCR modes, and why the seam exists

`OCR_ENGINE` selects one of three modes behind a single `Protocol`
(`api/app/ocr/base.py`). Two of the three are implemented; every implementation
returns the same thing, full text plus per-block bounding boxes.

| Mode | What it is | Needs credentials | Used for |
|---|---|---|---|
| `cloud` | Google Cloud Vision | Yes, a service-account JSON | Production, and every published measurement |
| `fake` | **One built-in sample label, returned for every image** (`api/app/ocr/fake.py`) | No | Booting and exercising the stack with no Cloud Vision account |
| `paddle` | Local PaddleOCR, no outbound calls | No | **Not implemented.** The documented on-prem path |

The seam is not architectural taste. It answers three separate problems, and
each would have forced it on its own.

**The firewall.** TTB's IT admin, verbatim:

> "our network blocks outbound traffic to a lot of domains, so keep that in mind
> if you're thinking about cloud APIs. During the scanning vendor pilot, half
> their features didn't work because our firewall blocked connections to their
> ML endpoints."

A hosted OCR provider is therefore a deployment risk, not a settled choice.
Behind an interface, moving to on-premise OCR is a configuration change rather
than a rewrite, which is why `paddle` is in the table at all. It is honest to
say the adapter is unwritten; it would not be honest to claim the problem is
solved.

**Testability.** The rule engine is where nearly all the logic lives, and it has
nothing to do with the network. The whole suite runs with no account, no key
and no quota, and a test that suddenly needs credentials is a signal that
something has reached past a boundary.

**Attribution.** The accuracy figures depend on holding OCR still. That is
done by a third engine used only in tests, `CorpusOcrEngine`
(`api/tests/support/corpus.py`), which replays the bounding boxes the corpus
renderer actually drew. A wrong verdict is then attributable to a rule rather
than to a misread character, which is why two accuracy numbers are published
above rather than one. It is not reachable through `OCR_ENGINE`.

**Extraction has no such seam, and that is a gap.** The LLM call that turns OCR
text into structured fields always goes to Anthropic. Tests inject a fake at
that boundary, so they run offline; a *running server* cannot. A fixture
extractor for the credential-free path is a small piece of work and is not
built.

### Three states, never two

A senior agent's example, verbatim from the brief: the label reads `STONE'S
THROW`, the application says `Stone's Throw`. Technically a mismatch; obviously
the same thing. A tool that calls that a failure gets ignored, so every field
resolves to PASS, NEEDS REVIEW or FAIL, and NEEDS REVIEW is where judgment
belongs.

A fourth outcome exists at the label level: **unreadable**. It is deliberately
not folded into FAIL. "We could not read this" is not "this label is
non-compliant": the label may be perfectly compliant and badly photographed,
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
engine that hardcodes the spirits rule, where alcohol content is always
required, emits
false violations on two of the three categories. The engine reads field lists
from configuration; only spirits is populated.

### Every regulatory value was verified against a primary source

No CFR section, threshold or required text in this repository was written from
memory. Each was checked against Cornell LII on 2026-08-09, and the statutory
warning text was copied rather than retyped. A hallucinated threshold produces a
confident, authoritative, wrong answer whose wrongness is invisible. Every
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
wrong. Ink *density* does not detect bold, because GOVERNMENT WARNING is uppercase and
the sentence beside it is not, so capitals moved the number as much as weight
did. And a compliant warning is legitimately smaller than the body copy, so an
80%-of-body-text threshold failed every clean label in the corpus. The corpus
found both.

**A geometric check with no measurement returns NEEDS REVIEW, never PASS.** A
check that silently passes when it did not run is a false PASS, and false PASSes
are the error class this product is scored on.

---

## Scope and trade-offs

**On the TTB seal.** The sign-in screen and the masthead carry the Bureau's
seal (`web/public/ttb-logo.svg`, taken from ttb.gov) so the screens read as
what they are meant to sit inside. **This is a prototype written against a
take-home brief. It is not a TTB product, it is not operated by or affiliated
with the Bureau, and no verdict it produces is an official determination.**

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
| **Real authentication** | The deployed URL is public, so there is a gate: one shared agent credential from the environment, in a signed HttpOnly cookie. That is all it is. No accounts, no password hash at rest, no reset, no roles, none of which the brief asks for, and all of which would mean storing credentials. It keeps the queue off the open web; it is not an identity system, and anyone holding the credential is simply "the agent" |
| **Persistence** | The brief says not to store anything sensitive. Nothing is stored. The review queue is seeded at boot from results recorded at build time and lives in memory, so a restart loses uploads and decisions and returns it to that seeded state, and the screen says so rather than implying otherwise. In-flight batch jobs are lost too, and the API says so when asked about one |
| **Absolute millimetre type size** | Physically underivable from an uncalibrated image. The proportional proxy ships instead, documented as a proxy |
| **PDF upload** | The design handoff lists it; the brief does not. A PDF is rejected by name, "This is a PDF… export the artwork as a JPG or PNG", rather than failing generically |
| **Image preprocessing (deskew, glare removal)** | The quality gate detects and reports these; correcting them is Phase 4 |
| **Vision-model escalation** | Would ship only if the corpus showed OCR failing on labels a human can read. It does not, so it has not |

### Known limitations

- **A label running out of frame is refused, even when every field on the
  visible part is readable.** Being able to read what is in shot says nothing
  about what is out of it, and the missing strip is exactly where a mandatory
  element could be hiding. The agent is told which edge is cut and asked for a
  reframed photo rather than given a verdict computed from part of a label.
- **A frame that is blurred, underexposed *and* noisy can be misreported.**
  Grain carries the same edge energy as the attenuated detail of a very dim
  sharp label, 1.079 against 1.082, so no threshold separates them. It does
  not occur anywhere in the degraded test set, and the OCR checks refuse the
  image regardless; what suffers is the stated cause. Measured in
  `docs/specs/pipeline.md` 2.1.
- **The corpus is rendered.** Ground truth is exact, which is why the accuracy
  numbers mean anything, and it does not stress OCR against foil, curved glass,
  or script faces. Real photographs belong in the corpus as an unscored smoke
  set; they are not there yet.
- **Prompt caching does not engage.** The system prompt is below Haiku 4.5's
  4,096-token minimum cacheable prefix. Padding the prompt to reach the
  threshold would be gaming a number, so it is reported on `/health` and left
  alone. It costs a little per request and changes no behaviour.
- **Glare on pure-white artwork is undetectable** by the luminance check, since
  a reflection has no headroom above white paper. Such an image falls through to
  the OCR checks and is reported unreadable for a different reason.
- **The credential-free path boots the stack but cannot demonstrate it.**
  `OCR_ENGINE=fake` returns one built-in sample label for every image, and
  field extraction has no fixture path at all, so `docker compose up` without
  an Anthropic key fails on every check, and with one it reports on the
  built-in sample rather than on the image uploaded. Two pieces of work would
  close this: registering per-image OCR fixtures, and a fixture extractor.
  Neither is built. The tests are unaffected; they inject fakes at both
  boundaries.
- **The frontend bundle is committed** under `api/app/static`, because Render's
  build context is `api/` and the container cannot reach `web/`. A UI change
  needs `npm run build` and a commit. The production shape is a separate Vercel
  deployment, per the tech spec.
- **`field_of_vision` reads panels from image geometry.** A front-and-back
  photograph works; a single photograph of a wrap-around label does not tell us
  what is on the other side.
- **A photograph above 2,000 px on its long edge is resampled before anything
  reads it.** That is what keeps a phone photograph inside the five-second
  budget, and it is a real trade-off: OCR sees fewer pixels than were uploaded.
  It did not move a verdict on any of the 95 curated and sample labels, none of
  which reach the cap, so the claim is only that resampling is harmless at the
  sizes measured. Very small print on a very large photograph is the case that
  would test it, and it is not in the corpus.
- **Two image checks are resolution-sensitive by construction.** Focus and
  border ink are measured in pixels, so what counts as blurred or as running
  off the frame depends on how big the image is. The border band is a fraction
  of the long edge for exactly this reason. Focus is not, and is therefore
  measured on whatever the OCR engine will read rather than on the upload,
  which is the more honest pairing but still a proxy.

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
| OCR | Google Cloud Vision, behind a `Protocol` | Fast, strong on stylised type, returns bounding boxes, which is what makes evidence crops possible |
| Extraction | Claude Haiku 4.5, structured outputs, thinking disabled, temperature 0 | Benchmarked against Opus 5 and Sonnet 5 during the spike. Structured outputs remove the parse-and-retry loop; temperature 0 because the same label must get the same verdict twice |
| Rules | Pure Python, no dependencies | Unit-testable with no network. The whole engine runs in 5 ms |
| Frontend | React 19, Vite, TypeScript, hand-written CSS tokens | The design specifies exact values throughout, and each is an accessibility decision with a reason |
| Tests | pytest, Vitest, Testing Library | 423 backend, 17 frontend |
| Hosting | Render, always-on tier, from `api/Dockerfile` | Cold starts sabotage the evaluator's first click |

---

## Repository

```
requirements.md          the brief, verbatim. Never edited
docs/
  PRD.md                 derived requirements, scope, test corpus
  tech-spec.md           stack and architecture
  ui-spec.md             screens, data shape, design resolutions
  build-loop.md          current state and the build procedure
  specs/                 rule-engine, pipeline, batch
docker-compose.yml       one command; fixture OCR, still needs an Anthropic key
api/
  Dockerfile             multi-stage; Render deploys from this
  app/rules/             the compliance engine, pure, no I/O
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

`.claude/rules/` holds the constraints this build was written under: verify
regulations against source, measure rather than claim, no generic failures, the
accessibility bar. They are worth reading if you want to know why the code looks
the way it does.
