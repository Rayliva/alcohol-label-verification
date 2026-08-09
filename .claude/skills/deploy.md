# Deploy

## When to use

Every merge to `main` deploys automatically. Use this for manual deploys, first-time setup, and verifying a deploy actually works.

Deploy **early and often** — a working public URL is a hard deliverable (D-4), and the most common way take-homes lose it is leaving deployment to the last day.

## Services

| Service | Platform | Source |
|---|---|---|
| API | Render, **paid always-on tier** | `api/Dockerfile` |
| Frontend | Vercel, free static | `web/` |

**The paid Render tier is a requirement.** The free tier sleeps after 15 minutes and takes ~50s to wake — an evaluator's first click would hit a cold instance and the 5-second claim dies on the spot.

## Commands

```bash
# TODO: confirm service names once created
git push origin main          # CI deploys both on green

# Manual
render deploys create <service-name>
cd web && vercel --prod
```

## Post-deploy verification — always run this

A deploy that returns 200 is not a deploy that works.

1. **Health check** — `curl https://<api>/health` returns 200.
2. **Warmup ran** — check startup logs for both calls: prompt cache and schema compilation.
3. **Cache is actually live** — logs must show `cache_read_input_tokens > 0` on the second warmup call. If it is zero, the prompt is below the model's minimum (512 tokens on Opus 5, **1,024 on Sonnet 5 and Haiku 4.5**) and caching is silently doing nothing.
4. **End-to-end** — upload one real label through the deployed UI and time it. Not a curl against the API; the actual path an evaluator takes.
5. **Cold-ish first click** — wait a few minutes, then click again. This is the evaluator's experience, and the one most easily missed by testing only while warm.

## Environment variables

Set in the Render dashboard, documented in `.env.example`:

| Variable | Notes |
|---|---|
| `ANTHROPIC_API_KEY` | |
| `EXTRACTION_MODEL` | Pinned to the benchmark winner |
| `OCR_ENGINE` | `cloud` in production |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Cloud Vision service account |
| `CORS_ORIGINS` | The Vercel URL |

## Common pitfalls

- **Free tier by accident.** Easy to select, fatal to the demo, and invisible until someone returns after a quiet period.
- **CORS.** The frontend is on a different origin; a preview deploy on a new Vercel URL will be blocked until it is added.
- **Secrets in the image.** Credentials come from the environment at runtime, never baked into the Docker build.
- **Deploying an unbenchmarked model.** `EXTRACTION_MODEL` should be the measured winner, not whatever was last used locally.
- **Verifying only while warm.** Test the cold path deliberately — it is the one the evaluator hits first.
