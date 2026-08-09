# Add a UI component

## When to use

Any new React component.

**The accessibility bar lives in [`.claude/rules/accessibility.md`](../rules/accessibility.md)** — nine numbered, checkable requirements. Read it before building; this skill is the how-to for satisfying it.

## Steps

1. Component in `web/src/components/<Name>.tsx`, typed props, no `any`.
2. Tailwind v4 utilities. Reuse existing tokens — don't introduce a new grey.
3. Test in `web/tests/` with Vitest + Testing Library. **Query by accessible role and label**, not test IDs — if `getByRole('button', { name: /check this label/i })` can't find it, a screen reader can't either.
4. Keyboard path: tab to it, activate with Enter/Space, visible focus ring. Never `outline: none` without a replacement.
5. Verify contrast on the real background, not in isolation.

## Verdict display specifics

The three states must be distinguishable **without color** — colorblind users, and Dave printing the page:

| Verdict | Color | Plus |
|---|---|---|
| PASS | green | check icon + the word "Pass" |
| NEEDS REVIEW | amber | warning icon + "Needs review" |
| FAIL | red | cross icon + "Fail" |

Every verdict shows declared value, detected value, and the evidence crop side by side. That layout is the answer to the trust problem — an agent distinguishes a genuine discrepancy from an OCR misread in about a second. Don't collapse it behind a click.

## Common pitfalls

- **Dense data tables.** The batch results table is the biggest risk — sort problems first, keep rows tall, don't shrink text to fit more in.
- **Spinners with no information.** For batch, show "47 of 200" and elapsed time, not an indeterminate spinner. A 3-minute unexplained spinner reads as broken.
- **Hover-only actions.** Invisible on touch, invisible to keyboard users, and easy to miss for anyone not hunting.
- **Icon-only buttons.** Always pair with a text label.
- **Disabled buttons with no explanation.** If the primary action is disabled, say why in adjacent text.
