# Generate or extend the test corpus

## When to use

Adding a violation variant, adding a beverage type, regenerating after a template change, or building the 200-label batch fixture.

## Why rendered, not AI-generated

Ground truth comes from programmatic rendering (HTML/SVG → PNG), not image generation. Image models cannot reliably render exact text, and this corpus needs a verbatim-correct government warning in one variant and a single altered word in another. The generator knows what it drew, so expected verdicts are derived, not hand-labeled.

## Commands

```bash
# TODO: confirm once corpus/generate.py exists
uv run python corpus/generate.py --all
uv run python corpus/generate.py --tier 2          # single-field violations
uv run python corpus/generate.py --id warning-title-case   # one label
uv run python corpus/generate.py --batch 200       # batch throughput fixture
```

## Corpus structure

| Tier | Purpose | Count |
|---|---|---|
| 1 | Clean baseline — 4 designs × 3 beverage types | 12 |
| 2 | Single-field violations | 28 |
| 3 | Conditional rules (wine/malt ABV, both directions) | 6 |
| 4 | Image quality — 6 degraded-but-readable, 6 unreadable | 12 |
| 5 | Same field of vision | 3 |
| 6 | Batch fixture (generated, throughput only) | 200 |
| 7 | Malformed manifests | 4 |

## Adding a violation variant

1. **One violation per label.** If a label breaks three rules and the tool misses one, you cannot tell which check failed. Multi-violation labels exist only in the realism set.
2. Add the variant to the generator with an explicit id (`warning-not-bold`, `abv-proof-mismatch`).
3. Declare its expected verdicts in `corpus/fixtures/expected.json` — every field, not just the broken one. A violation label must still PASS on its untouched fields; that is how false positives get caught.
4. Regenerate and run `uv run pytest api/tests/accuracy -m accuracy`.

## Common pitfalls

- **Forgetting the expected-verdict entry.** The label renders, the suite skips it silently, and coverage looks better than it is.
- **Only testing degraded-but-readable images.** Tier 4 is deliberately half unreadable. A tool that confidently hallucinates fields from mud passes the readable half and fails the product requirement (FR-15) — the unreadable half must produce a *specific reason*, not a generic failure.
- **Editing a rendered PNG by hand.** Ground truth then lives nowhere. Change the generator.
- **Scoring real photographs.** They belong in the corpus as qualitative smoke tests only; their ground truth is uncertain and including them corrupts the accuracy metric.
