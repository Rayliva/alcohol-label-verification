import type { Outcome } from "../api/types";

/**
 * A verdict, encoded three ways at once: colour, glyph, and word.
 *
 * All three, always. Colour alone disappears for a colourblind agent and on a
 * printed page, and the glyph alone means nothing to someone meeting it for the
 * first time (.claude/rules/accessibility.md, rule 5).
 */

const WORDING: Record<Outcome, { glyph: string; word: string }> = {
  pass: { glyph: "✓", word: "Pass" },
  needs_review: { glyph: "⚠", word: "Needs review" },
  fail: { glyph: "✕", word: "Fail" },
  unreadable: { glyph: "?", word: "Could not be read" },
};

export function VerdictBadge({
  verdict,
  small = false,
}: {
  verdict: Outcome;
  small?: boolean;
}) {
  const { glyph, word } = WORDING[verdict];
  return (
    <span className={`badge badge--${verdict}${small ? " badge--small" : ""}`}>
      <span className="badge__glyph" aria-hidden="true">
        {glyph}
      </span>
      {word}
    </span>
  );
}

export function verdictGlyph(verdict: Outcome): string {
  return WORDING[verdict].glyph;
}

export function verdictWord(verdict: Outcome): string {
  return WORDING[verdict].word;
}
