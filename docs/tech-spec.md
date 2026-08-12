# Tech Spec — AI-Powered Alcohol Label Verification

**Status:** Draft, bootstrap Phase 2
**Date:** 2026-08-09
**Depends on:** [`docs/PRD.md`](PRD.md) · **Source of truth:** [`requirements.md`](../requirements.md)

---

## Architecture

The core design decision: **do not put a vision model on the hot path.**

```
label image
    │
    ├─▶ preprocess (deskew, contrast, glare)          OpenCV      ~100ms
    │
    ├─▶ OCR → text + bounding boxes                   Cloud Vision ~300-800ms
    │        │
    │        ├─ low confidence? ──▶ vision escalation  Claude Opus 5  (off hot path)
    │        │
    ├─▶ field identification: text → structured JSON  Claude       ~500-1500ms
    │
    ├─▶ rule engine: fields → verdicts                pure Python  ~5ms
    │
    └─▶ evidence crops from bounding boxes            Pillow       ~50ms
```

Three properties fall out of this shape:

1. **Speed** — the LLM sees text, not pixels. Several times faster than a vision call (NFR-1).
2. **Evidence** — OCR bounding boxes are what make evidence crops possible at all (FR-13).
3. **Testability** — the compliance rules are pure functions over a `LabelData` struct. Unit-testable with no network, which is what the TDD rule requires.

Vision is the **escalation path** for degraded images, not the default.

---

## 1. Language & runtime

**Python 3.12** (backend) + **TypeScript 5.x on Node 22** (frontend build).

Python for the OpenCV and OCR ecosystem — image preprocessing (P1-11) and bounding-box handling are first-class there and awkward everywhere else.

## 2. Frameworks

- **Backend:** FastAPI + Pydantic v2, served by Uvicorn. Pydantic models double as the JSON schema for structured outputs — one definition, no drift.
- **Frontend:** React 19 + Vite. Vite over Next.js because the API is separate; SSR buys nothing and Next would add a second deployment concept.

## 3. Data layer

**None.** No database (OS-2). Batch progress lives in an in-memory job store keyed by job ID — a dict behind an interface, swappable for Redis if the process ever needs to scale beyond one. Not persistence.

## 4. Hosting / deployment

| Service | Platform | Note |
|---|---|---|
| API | Render, **paid always-on tier**, deployed from `api/Dockerfile` | Free tier sleeps after 15 min and takes ~50s to wake — fatal to the demo |
| Frontend | Vercel, free static | Superseded: the built bundle ships inside the API container from `api/app/static`, because Render's build context cannot reach `web/`. Vercel remains the production shape (README, Known limitations) |

The paid tier is a requirement, not a preference. Cold starts are risk #2 in the PRD. Container deployment (see §11) keeps the OpenCV system dependencies reproducible between local and production.

## 5. Auth

**Superseded** (see `docs/specs/review-queue.md`): the deployed URL is public,
so a demonstration gate shipped — one shared credential from the environment
in a signed HttpOnly session cookie. Still no accounts, no stored credentials,
no identity system; OS-1's spirit (no auth *system*) stands.

## 6. External services

### OCR — behind a swappable interface

```python
class OcrEngine(Protocol):
    def extract(self, image: bytes) -> OcrResult: ...   # text + bounding boxes
```

| Adapter | Role |
|---|---|
| `CloudVisionEngine` | Default. Google Cloud Vision — fast, strong on stylized type, returns boxes |
| `PaddleOcrEngine` | **Not written.** The on-prem path that would answer C-3; selecting it raises. P2 |
| `FakeOcrEngine` | One built-in sample label for every image. Runs the stack with no Cloud Vision account |

Selected by the `OCR_ENGINE` env var. What this buys against C-3 is the seam, not the engine: an on-prem OCR adapter is one implementation behind this `Protocol` rather than a rewrite. The adapter is not written, and the README says so — the constraint is a visible architecture decision, not a delivered capability.

### LLM — Anthropic API

Model is **config-driven** (`EXTRACTION_MODEL`). Benchmarked during the latency spike across `claude-opus-5`, `claude-sonnet-5`, and `claude-haiku-4-5`; the winner is pinned and the comparison table published in the README.

**Extraction call:**

```python
response = client.messages.parse(
    model=settings.extraction_model,
    max_tokens=2048,
    thinking={"type": "disabled"},        # legal at effort "high" or below
    output_config={"effort": "low"},
    system=[{"type": "text", "text": EXTRACTION_PROMPT,
             "cache_control": {"type": "ephemeral"}}],
    messages=[{"role": "user", "content": ocr_text}],
    output_format=ExtractedFields,        # Pydantic model
)
fields = response.parsed_output
```

- **Structured outputs** guarantee schema-valid JSON — no regex, no retry-on-parse loop.
- **Prompt caching** on the system prompt: identical across all 200 labels in a batch, so it is written once and read at ~0.1× cost thereafter. *As shipped this never engages*: the prompt is below Haiku 4.5's minimum cacheable prefix, `/health` reports it, and padding a prompt to game a cache was declined (README, Known limitations).
- **Thinking disabled at low effort** for latency. Benchmarked against `{"type": "adaptive"}` + `effort: "low"`; whichever wins on the corpus is what ships.

**Vision fallback:** `claude-opus-5` for degraded images — it has the high-resolution tier (2576px long edge), which matters for small warning text.

### Startup warming (two calls, and they must be separate)

**Why this exists.** The API is stateless — every call re-sends and re-processes the full system prompt. Prompt caching stores the processed form of that stable prefix so later calls read it at ~0.1× cost instead of reprocessing it. The cache starts empty after every deploy, so without warming the *first* request pays full latency — and that request is likely the evaluator's first click.

| Call | Warms | Why separate |
|---|---|---|
| `max_tokens=0`, cached system prompt, no `output_config.format` | Prompt cache | `max_tokens: 0` is **rejected** when combined with `output_config.format` |
| One tiny real extraction request | JSON schema compilation (cached 24h) | New schemas carry a one-time compile cost on first use |

```python
@asynccontextmanager
async def lifespan(app):
    await warm_prompt_cache()   # max_tokens=0, no schema
    await warm_schema()         # tiny real extraction
    scheduler.add_job(warm_prompt_cache, "interval", minutes=50)
    yield
```

Use `cache_control: {"type": "ephemeral", "ttl": "1h"}` with an hourly re-warm rather than the 5-minute default. The 1h TTL costs 2× on write vs 1.25×, negligible on a prompt this size, and it survives the gaps between an evaluator's visits — which is our actual access pattern.

**Startup checks for a cache hit.** Minimum cacheable prefix is **512 tokens on Opus 5, 1,024 on Sonnet 5, and 4,096 on Haiku 4.5**. Below the minimum, caching silently does nothing — no error, just `cache_creation_input_tokens: 0`. Warmup checks that the two counters are not both zero; if the prompt is too short for the selected model this is reported on `/health` as a note rather than failing the boot, because it costs a little per request and changes no behaviour. Caches are also per-model, so switching models starts cold.

### Thinking must always be explicit

Newer models reason internally before answering — valuable on hard problems, costly in latency. Field extraction from OCR text is not a hard problem, so thinking buys little here.

**On Opus 5 thinking is ON when unspecified; on the previous generation it was OFF.** A call site that omits the parameter therefore inherits a default that has already changed once, silently, with no error. Every request carries an explicit `thinking` value, enforced by a unit test on the request builder.

Thinking-disabled is comparatively safe for this call: its documented failure modes are tool calls leaking into plain text (inapplicable — no tools) and `<thinking>` tags leaking into output (largely neutralized by structured outputs constraining the response to the schema). Benchmarked against `adaptive` + `effort: "low"` regardless; the corpus decides.

## 7. Frontend stack

React 19 + Vite + TypeScript. **Tailwind CSS v4** for styling. **TanStack Query** for server state (batch progress polling); no global state library — there is very little client state.

UI must clear the NFR-2 bar: large targets, high contrast, one primary action per screen, no hidden state.

## 8. Testing stack

Per `.claude/rules/test-driven-development.md`, tests come first.

| Layer | Tool | Scope |
|---|---|---|
| Unit | pytest | Rule engine, matchers, normalizers, unit conversion. Pure functions, no network |
| Integration | pytest + `FakeOcrEngine` | Full pipeline against the corpus, mocked at the boundary |
| E2E | Playwright | Single-label flow and batch flow, once each |
| Frontend unit | Vitest + Testing Library | Verdict rendering, evidence crops, results table |
| Accuracy | pytest, corpus-driven | Asserts the ≥95% field-verdict target; fails the build if it regresses |

Mock at the boundary (`OcrEngine`, Anthropic client), never internal collaborators.

## 9. CI/CD

GitHub Actions.

- **On PR:** ruff (lint + format check), mypy, pytest with coverage, ESLint, tsc, Vitest, Playwright
- **On merge to main:** the above, then auto-deploy API to Render and frontend to Vercel
- The accuracy suite runs on every PR — a threshold regression is a build failure, not a surprise at demo time

## 10. Observability

- **Logging:** `structlog`, JSON to stdout, Render captures it. Per-request timing for every pipeline stage — preprocess, OCR, LLM, rules — because NFR-1 requires published numbers and we can't publish what we don't measure
- **Metrics:** in-process latency histogram exposed at `/metrics` (p50/p95/p99)
- **Error tracking:** none. Structured logs are sufficient at this scope

## 11. Local dev

```bash
# API
uv sync && uv run uvicorn app.main:app --reload

# Frontend
npm install && npm run dev
```

**uv** for Python dependency management. `.env.example` documents every variable. `OCR_ENGINE=fake` takes OCR off the network and needs no Cloud Vision account; checking a label still needs an `ANTHROPIC_API_KEY`, because extraction has no fixture path. The test suite needs neither credential, so contributors can run it immediately.

### Docker

The API **is** containerized; local dev is not.

```bash
ANTHROPIC_API_KEY=sk-ant-... docker compose up   # OCR_ENGINE=fake: no Cloud Vision, no OCR traffic
```

The driving reason is OpenCV, not deployment aesthetics: image preprocessing (P1-11) needs system libraries (`libGL`, `libglib2.0`) that Render's native Python runtime doesn't reliably provide, and discovering that at deploy time is expensive. Three things the container buys:

| Benefit | Why it matters here |
|---|---|
| Reliable OpenCV system deps | Preprocessing is a shipped feature, not an optional extra |
| The on-prem path stays open | PaddleOCR's native deps effectively require a container, so shipping one keeps the C-3 answer (P2, not written) a packaging step rather than a re-platforming |
| One-command reviewer path | `docker compose up` boots the full stack with faked OCR — see the README for what that does and does not prove |

`api/Dockerfile` is multi-stage: a build stage for dependencies, a slim runtime with only the OpenCV libs. Render deploys from it.

**Local dev stays native** (`uv run uvicorn --reload`) — the reload loop is faster and that's where the hours go. Compose is the reviewer path and the deploy artifact, not the daily workflow. The frontend needs no container; it's static files on Vercel.

## 12. Repo layout

Single repository, two packages.

```
requirements.md          the brief, verbatim
CLAUDE.md
docker-compose.yml       one-command reviewer path (OCR_ENGINE=fake)
docs/
  PRD.md  tech-spec.md  build-loop.md  specs/
api/
  Dockerfile             multi-stage; Render deploys from this
  app/
    main.py              FastAPI entrypoint
    ocr/                 OcrEngine protocol + adapters
    extraction/          LLM client, prompts, Pydantic schemas
    rules/               compliance engine — pure, no I/O
      beverage_types/    spirits.py, wine.py, malt.py (data-driven config)
      matchers.py        fuzzy, numeric, exact
      warning.py         government warning: text, caps, bold, proportion
    batch/               job store, worker pool
    evidence/            bounding-box crops
  tests/
web/
  src/
  tests/
corpus/
  generate.py            renders the labeled test corpus
  fixtures/              manifests + expected verdicts
```

`rules/` imports nothing from `ocr/` or `extraction/` — it takes a `LabelData` struct and returns verdicts. That boundary is what keeps it unit-testable.

## 13. Code style

- **Python:** ruff (lint + format, line length 100), mypy strict on `rules/` and `extraction/`
- **TypeScript:** ESLint + Prettier, `strict: true`
- **Conventions:** no bare excepts; all boundary I/O typed; every public function in `rules/` carries a docstring citing its CFR section
- Pre-commit hooks run ruff and prettier

## 14. Hard constraints from the PRD

| Constraint | How this stack honors it |
|---|---|
| **~5s p95 latency** (NFR-1) | Text-only LLM call; OCR chosen for speed; prompt caching; startup warming; per-stage timing published |
| **Cold starts** (risk #2) | Render paid always-on tier; both warming calls at boot |
| **No persistence** (C-2) | No database; in-memory job store only |
| **Firewall** (C-3) | `OcrEngine` interface with a documented local adapter |
| **UI for a 73-year-old** (NFR-2) | Large targets, high contrast, one action per screen |
| **All three beverage types** | `rules/beverage_types/` as data-driven config, not code paths |
| **Deployed public URL** (D-4) | Render + Vercel, deployed from day one, not at the end |

---

## Open questions

1. **Which model wins the benchmark** — resolved by the latency spike, before any UI work.
2. **Whether `thinking: disabled` beats `adaptive` + low effort** on this task — same spike.
3. **Cloud Vision vs. Azure Document Intelligence** — Cloud Vision is the default; if the spike shows it weak on stylized label type, the adapter interface makes the swap cheap.
4. **PaddleOCR adapter** — P2. Ships if the core lands early; documented as the on-prem path either way.
