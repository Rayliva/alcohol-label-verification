# AI-Powered Alcohol Label Verification

Prototype that verifies alcohol beverage label artwork against the data declared in a TTB COLA application. Take-home project.

Bootstrapped from the greenfield template.

## Read this first, every session

**[requirements.md](requirements.md) is the original take-home brief, verbatim.** Read it at the start of any session before planning, writing, or reviewing code.

It is the unaltered source material — stakeholder interviews, technical requirements, deliverables, evaluation criteria. Do not edit it, summarize it in place, or add analysis to it. It stays exactly as the client provided it.

If `requirements.md` and any later document disagree, **`requirements.md` wins.**

## Required reading

Before doing any non-trivial work, read every file in `.claude/rules/`. They define the methodology and constraints for this project.

**Methodology:**
- `.claude/rules/spec-driven-development.md` — specs precede code
- `.claude/rules/test-driven-development.md` — tests precede implementation

**Project constraints:**
- `.claude/rules/trace-to-brief.md` — every task traces to the brief or the PRD
- `.claude/rules/verify-regulations.md` — never cite a CFR section from memory
- `.claude/rules/measure-dont-claim.md` — no performance claim without a benchmark run
- `.claude/rules/error-handling.md` — failures name their cause; assert silent assumptions at boot
- `.claude/rules/secrets.md` — credentials from the environment only
- `.claude/rules/accessibility.md` — the nine checkable UI requirements

If a rule file is added or removed, update this list.

## Skills

Per-project skills live in `.claude/skills/`. Read `.claude/skills/INDEX.md` when starting a new task to see what is available.

## Workflow

Bootstrap is **complete**. Phase 0 is **complete**. Phase 1 is **in progress**.

**Start here: [`docs/build-loop.md`](docs/build-loop.md) opens with a CURRENT STATE section** — what is done, the next behaviours in order, environment gotchas, and decisions already settled. Read it before writing code. Run `/build` to continue the loop.

| Document | Contents |
|---|---|
| [`requirements.md`](requirements.md) | The brief, verbatim. Never edited |
| [`docs/PRD.md`](docs/PRD.md) | Derived requirements, personas, metrics, scope, test corpus |
| [`docs/tech-spec.md`](docs/tech-spec.md) | Stack, architecture, deployment |
| [`docs/ui-spec.md`](docs/ui-spec.md) | Screens, data shape, design-review resolutions |
| [`docs/build-loop.md`](docs/build-loop.md) | **Current state + build procedure** |
| [`README.md`](README.md) | Approach, measured numbers, limitations |

Quick orientation:

- **Live API:** https://alcohol-label-verification-3sn4.onrender.com/health — pushing to `main` auto-deploys
- **Run tests:** from `api/`, `.venv/Scripts/python.exe -m pytest -q` (Windows paths; `uv` is `python -m uv`)
- **No credentials needed:** `OCR_ENGINE=fake` runs the whole stack offline
- **Never read, print, or commit `.env`**

Derived requirements, scope decisions, and assumptions belong in `docs/PRD.md` and the README — **never** in `requirements.md`.

## Project-specific notes

- Do not add features the brief does not call for. Propose first.
- Check work against `requirements.md` before and after each task — confirm the task traces to something the brief actually asks for, and that nothing in the brief was quietly dropped or narrowed.
