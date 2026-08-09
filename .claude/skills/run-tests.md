# Run tests

## When to use

Before every commit, after every red→green cycle, and whenever you need to know whether a change broke the accuracy target.

## Commands

```bash
# Backend — all Python tests
uv run pytest

# One tier, while iterating on a single behavior
uv run pytest api/tests/unit/rules/           # pure rule logic, no network
uv run pytest api/tests/integration/          # pipeline with FakeOcrEngine
uv run pytest api/tests/unit -k warning       # single behavior by keyword

# Accuracy suite — asserts the >=95% field-verdict target against the corpus
uv run pytest api/tests/accuracy -m accuracy

# Frontend
cd web && npm run test           # Vitest, watch mode
cd web && npm run test -- --run  # single pass, for CI parity

# E2E
cd web && npx playwright test
cd web && npx playwright test --ui   # debugging a failing flow
```

## Rules of thumb

- **Unit tests must never touch the network.** `api/tests/unit/rules/` imports only from `app/rules/`. If a test there needs a mock of the Anthropic client, the code under test is in the wrong module.
- **Set `OCR_ENGINE=fake`** for integration tests. It is the default in `api/tests/conftest.py`; if a test suddenly needs credentials, something is reaching past the boundary.
- **The accuracy suite is slow** (it runs the whole curated corpus). Run it before pushing, not on every save.
- Run the full suite before any commit that touches `app/rules/` — that package has the widest blast radius.

## Common pitfalls

- **Accuracy suite fails after a threshold change.** Expected. Either the change is wrong, or the corpus expectations need updating — decide which, don't just move the threshold until it passes.
- **Playwright fails on a cold API.** The dev server does not run the warmup path. Give the first test a longer timeout, or hit `/health` before the suite.
- **Vitest passes locally, fails in CI.** Usually watch-mode state. Reproduce with `npm run test -- --run`.
- A test that mocks `app.rules` internals is testing the wrong thing — mock at `OcrEngine` or the Anthropic client, never inside the rule engine.
