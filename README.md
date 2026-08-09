# AI-Powered Alcohol Label Verification

Verifies alcohol beverage label artwork against the data declared in a TTB COLA application. For each required field it returns a **PASS / NEEDS REVIEW / FAIL** verdict with the cropped region of the image that justifies it, so a compliance agent can confirm or override at a glance.

> **Status:** in development. Measured performance numbers, the deployed URL, and full setup instructions land as the build progresses. Sections marked _TBD_ are not yet written rather than omitted.

**Live API:** https://alcohol-label-verification-3sn4.onrender.com/health
**Live demo:** _UI pending — Phase 2_

---

## Approach

The core decision: **the language model never sees the image on the hot path.**

```
label image
  → preprocess (deskew, contrast, glare)     OpenCV
  → OCR: text + bounding boxes               Cloud Vision
  → field identification: text → JSON        Claude (structured outputs)
  → compliance rules → verdicts              pure Python
  → evidence crops from bounding boxes       Pillow
```

Three things follow from that shape:

1. **Speed.** A text-only model call is several times faster than a vision call. The brief's hard requirement is ~5 seconds per label — a prior vendor pilot took 30–40s and agents abandoned it.
2. **Evidence.** OCR bounding boxes are what make the evidence crops possible. The feature that earns an agent's trust and the design that makes it fast come from the same choice.
3. **Testability.** The compliance rules are pure functions over a struct — no network, no mocks — so the regulations can be tested exhaustively against a labeled corpus.

Vision is the **escalation path** for degraded images, not the default.

_Full detail: [`docs/tech-spec.md`](docs/tech-spec.md). Scope and assumptions: [`docs/PRD.md`](docs/PRD.md)._

---

## Setup

_TBD — written once the scaffolding lands._

```bash
cp .env.example .env    # then fill in your keys
```

Every variable is documented in [`.env.example`](.env.example). To run with no credentials at all, set `OCR_ENGINE=fake` — the whole stack runs against deterministic fixtures with no network access.

---

## Security and secrets handling

Credentials are injected as **runtime environment variables** and are never committed, logged, or baked into container images.

| Environment | Source |
|---|---|
| Local development | `.env`, gitignored |
| Production | Render environment variables — encrypted at rest, injected at runtime |
| CI | GitHub Actions repository secrets |

The application reads only from the process environment; `.env` is a local-development convenience, not something the code knows about. Both `.gitignore` and `.dockerignore` exclude it — the latter matters because git rules do not apply to the Docker build context, and a `COPY . .` would otherwise bake credentials into the image.

Logs record whether a credential is *present*, never its value.

**For a production federal deployment** this would move to a managed secrets service — Azure Key Vault, given TTB's Azure environment — with rotation policy and access logging, per NIST SP 800-53 authenticator-management and protection-at-rest controls. That is deliberately out of scope for a prototype the brief scopes as standalone and non-sensitive.

**The application stores nothing.** No database, no document retention, no user accounts, no PII. Uploaded images live in memory for the duration of a request; batch job state is in-process and discarded when the job completes.

### Production considerations (not built)

Deliberately out of scope, listed because a reviewer should see they were considered rather than missed:

| Concern | Prototype | Production |
|---|---|---|
| **Authentication** | None. An optional "your name or initials" field attributes overrides within a session | Agency SSO / PIV card, role separation between agent and supervisor, session management |
| **Audit logging** | None — overrides live in session memory and are discarded | Immutable per-decision audit trail: who overrode what, when, and why |
| **Secrets** | Runtime environment variables | Managed secrets service with rotation and access logging |
| **Data retention** | Nothing persisted | Retention policy aligned to federal records schedules |
| **Network** | Public cloud with outbound API calls | On-prem or FedRAMP-authorized boundary; `OCR_ENGINE=paddle` removes outbound OCR calls |

No authentication was built because the brief does not ask for it, and a credential store would contradict the "not storing anything sensitive" constraint. A hardcoded or cosmetic login would be worse than none on a compliance tool.

---

## Network dependencies

OCR runs behind a swappable interface with three adapters:

| `OCR_ENGINE` | Behavior |
|---|---|
| `cloud` | Google Cloud Vision. Default in production |
| `paddle` | Local PaddleOCR — **no outbound calls** |
| `fake` | Deterministic fixtures — no keys, no network |

The brief notes that TTB's network blocks outbound traffic to many domains. That does not affect this hosted prototype — the browser talks to our server, and our server makes its own outbound calls from its own network — but it would matter for a deployment inside TTB's environment. Setting `OCR_ENGINE=paddle` runs the pipeline with no external calls and requires no other code changes.

---

## Performance

| Metric | Target | Measured |
|---|---|---|
| Single label, p95 | < 5s | **2,528 ms** ✅ |
| Field verdict accuracy | ≥ 95% | _pending corpus_ |
| False PASS on warning violations | 0 | _pending corpus_ |
| Batch of 200 | completes | _pending_ |
| Deployed and always-on | required | **live**, ~150 ms to `/health` |

### End-to-end pipeline (2026-08-09)

Real measurement, not the sum of stage estimates. Warm caches, `claude-haiku-4-5`, thinking disabled, Cloud Vision OCR, n=20 on a rendered spirits label.

| Stage | p50 | p90 | p95 | max |
|---|---|---|---|---|
| OCR (Cloud Vision) | 260 ms | 288 ms | 292 ms | 316 ms |
| Field extraction (LLM) | 1,614 ms | 2,193 ms | 2,242 ms | 2,733 ms |
| **Total** | **1,891 ms** | **2,452 ms** | **2,528 ms** | **2,999 ms** |

Zero of twenty runs exceeded the 5-second target; the slowest was 2,999 ms. That leaves roughly 2 seconds of headroom for the compliance rules (microseconds — pure Python over a struct) and evidence cropping.

**OCR came in well under its estimate.** Vendor documentation suggested 300–800 ms; measured p95 is 292 ms, and OCR is only ~11% of total time. The architecture's premise — keep the model on text, not pixels — is what makes the budget comfortable rather than tight.

**A methodology note worth stating.** An earlier run at n=8 reported p95 5,211 ms and appeared to fail the target. At n=8 the p95 index *is* the maximum, so that figure was "the worst of eight," not a p95 — one network outlier defined it. Re-running at n=20 gave 2,528 ms with nothing above 3 s. Small-sample tail metrics are not tail metrics.

### Model selection (Phase 0 spike, 2026-08-09)

Field extraction measured on the **LLM leg only**, before OCR was available. Warm cache, `effort: low`, 6–8 runs per arm, structured outputs enabled. Note the same small-sample caveat applies to the p95 column here — it is directionally right, and the ranking held, but treat p50 as the more reliable figure.

| Model | Thinking | p50 | p95 | Exact-field match | Prompt cache |
|---|---|---|---|---|---|
| **Haiku 4.5** | off | **1,732 ms** | **3,160 ms** | 6/6 | not engaging |
| Sonnet 5 | off | 3,449 ms | 3,894 ms | 6/6 | yes |
| Sonnet 5 | adaptive | 3,936 ms | 4,067 ms | 6/6 | yes |
| Opus 5 | off | 5,032 ms | 5,338 ms | 6/6 | yes |
| Opus 5 | adaptive | 4,199 ms | 12,837 ms | 6/6 | yes |

**Decision: Haiku 4.5 with thinking disabled.** It is ~3× faster than Opus 5 and matched it on this sample. Extracting named fields from OCR text is an easy task — OCR has already done the hard part — so the capability headroom of a larger model buys nothing here and costs the entire latency budget.

Three findings worth recording:

- **Opus 5 cannot meet the budget on this path.** At p95 5,338 ms it exceeds the 5-second target *before* OCR is added. It remains the vision fallback, where it sits off the hot path.
- **Adaptive thinking hurts, and its tail is worse than its median.** Opus 5's p50 was reasonable at 4,199 ms while one call took 12,837 ms. A mean would have hidden that; p95 is the metric the requirement names for exactly this reason.
- **Haiku 4.5's prompt cache does not engage** — its minimum cacheable prefix exceeds our ~1.2K-token system prompt, so nothing is cached and no error is raised. Accepted rather than worked around: padding a prompt to reach a cache threshold trades clarity for a saving that is negligible at Haiku's input price. The startup assertion still fails loudly if caching is expected and absent.

**Honest limits of this measurement.** Accuracy is one clean rendered label across six fields, which proves the plumbing rather than the accuracy target — the real number comes from the labeled corpus in Phase 1. OCR latency (~300–800 ms per vendor documentation) is still unverified, pending Cloud Vision credentials. Projected full-pipeline p95 is therefore ~3.9 s for Haiku and ~4.7 s for Sonnet; Sonnet 5 is the fallback if corpus accuracy disappoints.

---

## Limitations and trade-offs

_TBD — expanded as decisions are made. Known so far:_

- **Absolute type-size verification is not implemented.** 27 CFR 16.22 sets minimum type sizes in millimetres, which cannot be derived from an uncalibrated photograph — pixels convert to millimetres only with the container's real dimensions, which the input does not provide. A **proportional** check ships instead, flagging warning text that is disproportionately small relative to surrounding text. This catches the actual abuse pattern; it does not prove millimetre compliance, and it is reported as NEEDS REVIEW rather than FAIL.
- **Bold detection is heuristic**, based on relative stroke weight against adjacent body text rather than font metadata.
- **Beverage type coverage** — distilled spirits is implemented end to end. Wine and malt beverage rule sets are configuration entries; see [`docs/PRD.md`](docs/PRD.md) for current status.

---

## Documentation

| Document | Contents |
|---|---|
| [`requirements.md`](requirements.md) | The original brief, verbatim and unedited |
| [`docs/PRD.md`](docs/PRD.md) | Derived requirements, scope, assumptions, test corpus |
| [`docs/tech-spec.md`](docs/tech-spec.md) | Stack, architecture, deployment |
| [`docs/ui-spec.md`](docs/ui-spec.md) | Screens, states, accessibility constraints |
| [`docs/build-loop.md`](docs/build-loop.md) | Build procedure |
