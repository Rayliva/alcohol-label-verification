# Measure, don't claim

No performance or accuracy claim without a measurement behind it.

## The rule

1. **Every number published in the README comes from a benchmark run**, with the date and the corpus it ran against.
2. **No qualitative performance adjectives** in docs or comments — "fast", "efficient", "lightweight" are not claims, they are hopes.
3. **Report the metric the requirement names.** The PRD target is **p95 < 5s**, so publish p95. A mean that hides a bad tail does not satisfy it.
4. **State what was not measured.** An honest gap beats an implied guarantee.

## Why

The brief's most emphasized number is the 5-second budget, and it comes with a failure story: a vendor pilot ran 30–40s and agents abandoned it. A README that says "fast" invites the reader to assume we never checked. A README with real numbers — including unflattering ones — is worth more than a broader feature set with none.

Measurement also catches the silent failure modes in this stack. An undersized prompt does not error, it just stops caching. An omitted `thinking` parameter does not error, it just spends seconds. Only the numbers reveal these.

## Examples

**Do:**

> Single label: p50 1.9s, p95 3.4s, measured over the 61-label curated corpus on 2026-08-14 (Haiku 4.5, warm cache). Batch of 200: 4m12s at 8-way concurrency.

**Do** — publish the unflattering number and explain it:

> Cold first request: 6.1s, exceeding the 5s target. Mitigated by startup warming; the deployed instance never serves an unwarmed request.

**Don't:**

> The pipeline is optimized for low latency and typically responds well within the target.

Nothing here is checkable.

**Don't** — quote a number measured under different conditions than the claim implies. A warm-cache p95 presented as general performance is a misleading measurement, which is worse than none.
