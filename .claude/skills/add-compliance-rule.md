# Add a compliance rule

## When to use

Adding or changing any check in `api/app/rules/` — a new field verdict, a matching behavior, a beverage-type conditional. This is the most frequently repeated task in the build.

## Before writing code

Read the relevant section of [`requirements.md`](../../requirements.md) and confirm the rule traces to something the brief or the CFR actually requires. Then write or update the feature spec at `docs/specs/<feature>.md` per `.claude/rules/spec-driven-development.md`.

**Verify the regulation.** Never write a CFR citation from memory. The relevant parts:

| Beverage | Part | Mandatory fields | ABV |
|---|---|---|---|
| Distilled spirits | 27 CFR 5 | §5.63 | §5.65 |
| Wine | 27 CFR 4 | §4.32 | §4.36 |
| Malt beverages | 27 CFR 7 | §7.63 | conditional |
| Health warning | 27 CFR 16 | §16.21 text | §16.22 format |

## Steps

1. **Red.** Add a failing test in `api/tests/unit/rules/`. One behavior per test, named for the observable outcome:

   ```python
   def test_title_case_government_warning_fails():
       result = check_warning(label_with("Government Warning: (1) According to..."))
       assert result.verdict is Verdict.FAIL
       assert "capital letters" in result.reason
   ```

   Run it. Confirm it fails **for the right reason** — not an import error.

2. **Green.** Minimum implementation in `api/app/rules/`. No speculative abstraction.

3. **Refactor** with the test as a safety net.

4. **Add a corpus label** covering the case (see `generate-corpus`), so the accuracy suite exercises it end to end.

## Conventions

- **`rules/` is pure.** It imports nothing from `ocr/` or `extraction/`. Input is a `LabelData` struct; output is verdicts. If you need an HTTP call here, the design is wrong.
- **Every public function carries a docstring citing its CFR section**, e.g. `"""Verify net contents per 27 CFR 5.70."""`
- **Return three states.** `Verdict.PASS | NEEDS_REVIEW | FAIL` — never a bool. Binary verdicts are explicitly wrong for this product (PRD FR-11).
- **Every verdict carries a human-readable `reason`.** It is rendered in the UI; write it for Dave, not for a log.
- **The government warning is exact.** Whitespace normalization only, then character comparison. Fuzzy matching anywhere near `rules/warning.py` is a bug.

## Common pitfalls

- **Applying the regulatory ABV tolerance to a form-vs-label comparison.** Those tolerances (spirits ±0.3, wine ±1.5/±1.0) govern label vs *actual liquid*, lab-verified. Application and label are both documents and should agree exactly. Any difference is at minimum `NEEDS_REVIEW`.
- **Hardcoding spirits behavior.** Wine ≤14% ABV may omit the percentage if it says "table wine"; plain malt beverages need no ABV at all. A rule that assumes ABV is always required produces false violations on two of three categories.
- **Testing the implementation instead of the behavior.** Assert on the verdict and reason, never on internal state or private helpers.
- **Skipping the corpus label.** A unit test proves the function works; only a corpus label proves the pipeline routes to it.
