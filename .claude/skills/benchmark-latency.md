# Benchmark latency and model choice

## When to use

The day-one spike, before any UI work. Then again after any pipeline change, and once more before shipping to produce the README numbers.

Latency is the top risk in the PRD: p95 under 5 seconds, measured and published. A prior vendor pilot took 30–40s and agents abandoned it.

## What the spike must answer

1. **Which model** — `claude-opus-5` vs `claude-sonnet-5` vs `claude-haiku-4-5` on both latency *and* accuracy against the corpus.
2. **Thinking off vs adaptive at low effort** — on Opus 5, thinking is ON when unspecified. Measure both explicitly.
3. **Where the time actually goes** — per-stage: preprocess, OCR, LLM, rules, crops.

## Commands

```bash
# TODO: confirm once the harness exists
uv run python -m app.bench --model claude-opus-5 --n 50
uv run python -m app.bench --compare-models          # all three, same corpus
uv run python -m app.bench --thinking off,adaptive-low
uv run python -m app.bench --stages                  # per-stage breakdown
```

## Method

- **Run against the curated corpus**, not one hand-picked clean label. Latency on a clean render is not the number that matters.
- **Report p95, not mean.** The PRD target is p95 < 5s. A good mean with a bad tail still fails the agent's experience.
- **Warm before measuring.** An unwarmed first call includes cache population and schema compilation and is not representative — but *do* record it separately, because it is what an unwarmed deploy would show a user.
- **Verify caching is live.** Assert `cache_read_input_tokens > 0` after the first call. Minimums are 512 tokens on Opus 5 but **1,024 on Sonnet 5 and Haiku 4.5** — below the minimum, caching silently does nothing and the benchmark measures an uncached path without telling you.
- **Accuracy alongside latency.** A model that is 800ms faster and 6 points less accurate is not the winner. Report both in one table.

## Output

A markdown table committed to the README:

| Model | Thinking | p50 | p95 | Field accuracy | $/1k labels |
|---|---|---|---|---|---|

Plus the per-stage breakdown, so a reader can see where the budget goes.

## Common pitfalls

- **Measuring on a warm cache and reporting it as cold-start performance**, or vice versa. Label which is which.
- **Benchmarking without pinning the corpus version.** Regenerate the corpus and the numbers move for reasons unrelated to the code.
- **Forgetting the model config is per-model cached.** Switching `EXTRACTION_MODEL` starts cold; the first call after a switch is not comparable.
- **Optimizing the LLM stage when OCR is the bottleneck.** Run `--stages` first; the assumption that the model call dominates is exactly the kind of thing this spike exists to check.
