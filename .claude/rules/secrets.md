# Secrets

Credentials come from the environment. Nowhere else.

## The rule

1. **No secret in source, ever** — not committed, not in a comment, not as a "temporary" default.
2. **No secret baked into a Docker image.** Credentials are injected at runtime, never at build time. No `ENV ANTHROPIC_API_KEY=` in a Dockerfile, no secret passed as a build arg.
3. **No secret in logs.** Log the *presence* of a credential, never its value or a prefix of it.
4. **`.env` is gitignored; `.env.example` is committed** with every variable listed and every value blank or obviously fake.
5. **No secret in corpus fixtures or test data.** Tests run with `OCR_ENGINE=fake` and need no credentials at all.

## Credentials in this project

| Variable | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | Field extraction, vision fallback |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Cloud Vision OCR |
| `RENDER_API_KEY` | Deploy (CI only, GitHub secret) |

## Why

Beyond the obvious: this is a public repository submitted for review. A leaked key in git history is visible, permanent without a rewrite, and a poor look on a compliance tool. The brief also notes PII and retention considerations — we avoid the whole category by storing nothing (C-2), and credentials are the one sensitive thing we do handle.

## Examples

**Do:**

```python
api_key = settings.anthropic_api_key   # pydantic-settings, from env
if not api_key:
    raise StartupError("ANTHROPIC_API_KEY is not set")
```

**Do** — log presence, not value:

```python
log.info("anthropic_client_initialized", key_present=bool(api_key))
```

**Don't:**

```python
api_key = os.getenv("ANTHROPIC_API_KEY", "sk-ant-...")   # committed fallback
log.debug("using key", key=api_key[:12])                  # prefix is still a leak
```

**Don't** commit a `.env` with real values and plan to scrub it later. Git history keeps it. If a key is ever committed, rotate it — deleting the line is not a fix.
