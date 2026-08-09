# Skills

Per-project how-to guides for this stack. Read the one that matches your task before starting.

For *constraints* on how work is done — spec-first, test-first — see `.claude/rules/` instead. Skills are how-to; rules are non-negotiable.

| Skill | Use when |
|---|---|
| [run-tests](run-tests.md) | Running any test tier — unit, integration, E2E, or the corpus accuracy suite |
| [add-compliance-rule](add-compliance-rule.md) | Adding or changing a check in `rules/`. The most repeated task in the build |
| [add-beverage-type](add-beverage-type.md) | Editing the spirits / wine / malt rule sets, which are config rather than code |
| [generate-corpus](generate-corpus.md) | Adding a violation variant or regenerating the labeled test corpus |
| [benchmark-latency](benchmark-latency.md) | Measuring p95, comparing models, producing the README numbers |
| [debug-verdict](debug-verdict.md) | A field returned the wrong verdict and you need to localize the cause |
| [swap-ocr-engine](swap-ocr-engine.md) | Implementing or switching an `OcrEngine` adapter |
| [deploy](deploy.md) | Deploying to Render + Vercel and verifying the deploy actually works |
| [add-ui-component](add-ui-component.md) | Any new React component — encodes the accessibility bar |

## Open TODOs

Several skills reference commands that don't exist yet. Fill these in as the build creates them rather than inventing them now:

- `corpus/generate.py` CLI flags — [generate-corpus](generate-corpus.md)
- `app.bench` harness invocation — [benchmark-latency](benchmark-latency.md)
- `app.debug` CLI — [debug-verdict](debug-verdict.md)
- Render service name — [deploy](deploy.md)
