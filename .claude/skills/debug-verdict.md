# Debug a verdict

## When to use

A field returned the wrong verdict — a false FAIL, a missed violation, or a NEEDS REVIEW that should have been decisive.

## The key question

**Is this a extraction problem or a rule problem?** Almost every wrong verdict is one or the other, and they have completely different fixes. Answer this first; it saves most of the debugging time.

## Steps

1. **Look at the evidence crop.** It shows the region of the image the value came from. If the crop shows `45%` and the detected value is `4S%`, that is OCR — stop looking at the rule engine.

2. **Dump the pipeline stages** for the failing label:

   ```bash
   # TODO: confirm once the CLI exists
   uv run python -m app.debug --label corpus/out/warning-title-case.png --verbose
   ```

   This prints raw OCR text with bounding boxes, the extracted field JSON, and each verdict with its reason.

3. **Localize:**

   | Symptom | Cause | Fix |
   |---|---|---|
   | OCR text is wrong | Extraction | Preprocessing, or escalate to vision fallback |
   | OCR text right, extracted JSON wrong | Field identification | Extraction prompt or schema |
   | JSON right, verdict wrong | Rule engine | `rules/` — write a failing unit test first |
   | Verdict right, reason unhelpful | Presentation | The `reason` string |

4. **Reproduce in a unit test before fixing.** Per `.claude/rules/test-driven-development.md`, the bug report is the spec: write the failing test, then fix. The test stays in the suite.

## Reading the three states

- **False FAIL** — costs an agent seconds, but erodes trust fastest. Usually a threshold set too tight, or a normalization step missing (curly apostrophe, non-breaking space, unit variant).
- **Missed violation (false PASS)** — the expensive error. On the government warning the target is zero. Check normalization isn't being applied where it shouldn't: whitespace only, never case or punctuation.
- **Unnecessary NEEDS REVIEW** — the band is 0.80–0.95 by default. If a whole class of labels lands here, the normalizer is probably missing a case rather than the threshold being wrong.

## Common pitfalls

- **Tuning a threshold to fix one label.** Check the whole corpus after any threshold change — moving a boundary to fix one case routinely breaks three others. Run the accuracy suite, not the single test.
- **Fixing OCR noise in the rule engine.** If `rules/` starts accumulating "handle the case where OCR returned a zero for an O" logic, the fix belongs in normalization or preprocessing. `rules/` should stay a clean expression of the regulation.
- **Debugging without the crop.** The crop distinguishes "the label is wrong" from "we read it wrong" in about a second. It exists for exactly this.
