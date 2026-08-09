# Trace to the brief

Every piece of work traces to something the client actually asked for.

## The rule

Before starting a task, identify what it traces to: a line in [`requirements.md`](../../requirements.md), or a numbered item in [`docs/PRD.md`](../../docs/PRD.md). If it traces to neither, **propose it before building it**.

After finishing a task, check the reverse direction: did anything in the brief get quietly dropped or narrowed?

## Document boundaries

| Document | Contains | Editable |
|---|---|---|
| `requirements.md` | The original brief, verbatim | **Never.** Not edited, summarized in place, or annotated |
| `docs/PRD.md` | Derived requirements, scope decisions, assumptions | Yes |
| `docs/tech-spec.md` | Technical choices | Yes |
| README | Trade-offs, limitations, measured results | Yes |

If `requirements.md` and any later document disagree, **`requirements.md` wins** and the derived document gets corrected.

## Why

The brief is deliberately noisy — stakeholder chatter mixed with real requirements. Two failure modes follow, and this rule guards both: building things nobody asked for, and silently dropping things they did. "Attention to requirements" is an explicit evaluation criterion.

## Examples

**Do** — cite the trace in the commit or PR body:

> Adds proportional size check for the warning statement. Traces to FR-10 (PRD) and Jenny Park's "smaller font, burying it in tiny text" (requirements.md).

**Do** — flag a scope reduction explicitly rather than absorbing it:

> Bold detection ships as relative stroke-weight analysis, not absolute measurement. Documented as a limitation in the README per D-5.

**Don't** — add capability because it seems useful:

> Added a label history view so agents can see previously reviewed labels.

Nothing in the brief asks for this, and it contradicts C-2 (no persistence). Propose first.

**Don't** — record a derived decision in `requirements.md`. Assumptions go in the PRD.
