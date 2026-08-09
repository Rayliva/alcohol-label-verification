# Accessibility

The UI must clear the brief's stated bar: *"something my mother could figure out — she's 73."*

## The rule

Enforceable in review. Every one of these is checkable on a rendered component.

| # | Requirement | Threshold |
|---|---|---|
| 1 | Interactive target size | ≥ 44 × 44 px |
| 2 | Body text | ≥ 16px; nothing below 14px anywhere |
| 3 | Contrast | WCAG AA — 4.5:1 body, 3:1 large text and UI borders |
| 4 | Primary action | Exactly one visually dominant action per screen |
| 5 | No hidden state | No hover-only affordances, no meaning carried by color alone, no important content behind disclosure |
| 6 | Keyboard | Every action reachable by Tab, activated by Enter/Space, with a visible focus ring |
| 7 | Accessible names | Every control queryable by `getByRole(role, { name })`. No icon-only buttons |
| 8 | Progress | Determinate where the total is known — "47 of 200", not a spinner |
| 9 | Disabled controls | Never disabled without adjacent text explaining why |

## Why

Half the compliance team is over 50; one agent still prints his emails. The brief names ease of use as a requirement and the evaluation criteria score "user experience" explicitly. Rule 5 also serves the colorblind case and anyone printing a results page — the three verdict states must be distinguishable without color.

## Examples

**Do** — verdicts carry icon, text, and color:

```tsx
<span className="text-amber-700">
  <WarningIcon aria-hidden /> Needs review
</span>
```

**Do** — query by role in tests, which proves the accessible name exists:

```tsx
getByRole("button", { name: /check this label/i })
```

**Don't:**

```tsx
<button className="p-1" onClick={run}><PlayIcon /></button>
```

Target too small, no accessible name, meaning conveyed by icon alone.

**Don't** rely on a red/green dot to convey PASS vs FAIL. Colorblind users and printed pages both lose the entire result.

## See also

[`.claude/skills/add-ui-component.md`](../skills/add-ui-component.md) — the how-to for building a component against this bar.
