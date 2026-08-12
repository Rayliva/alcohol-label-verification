import type { FieldOutcome, WarningSubCheck } from "../api/types";
import { EvidenceCrop } from "./EvidenceCrop";
import { VerdictBadge } from "./VerdictBadge";

/**
 * The government warning, given more room than any other field.
 *
 * It is the only exact-match check in the product and it has six ways to fail,
 * so one badge on one row would hide which rule was broken. The detected text
 * is shown in full with any difference from 27 CFR 16.21 marked inline, not in
 * a separate diff view an agent has to open.
 */

/** The statutory text, for highlighting differences inline. */
export const STATUTORY_WARNING =
  "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not " +
  "drink alcoholic beverages during pregnancy because of the risk of birth defects. " +
  "(2) Consumption of alcoholic beverages impairs your ability to drive a car or " +
  "operate machinery, and may cause health problems.";

/**
 * Word-level difference against the statute.
 *
 * Deliberately case-sensitive: "Government Warning" in title case is a
 * violation, and a highlighter that folded case would render the one violation
 * this product is most often asked about as a perfect match.
 */
export function highlightDifferences(detected: string): { text: string; differs: boolean }[] {
  const expected = STATUTORY_WARNING.split(/\s+/);
  const actual = detected.trim().split(/\s+/);
  const segments: { text: string; differs: boolean }[] = [];

  // Both lengths, not just the label's. A warning cut short would otherwise
  // never be compared against the words it is missing, and the screen would
  // say the wording "matches the required text exactly" about a truncated
  // statement: a false PASS on the one exact check in the product.
  const length = Math.max(expected.length, actual.length);
  for (let index = 0; index < length; index += 1) {
    const word = index < actual.length ? actual[index] : `[missing: ${expected[index]}]`;
    const differs = expected[index] !== actual[index];
    const last = segments[segments.length - 1];
    if (last && last.differs === differs) {
      last.text += ` ${word}`;
    } else {
      segments.push({ text: word, differs });
    }
  }
  return segments;
}

export function WarningBlock({
  field,
  checks,
}: {
  field: FieldOutcome;
  checks: WarningSubCheck[];
}) {
  const detected = field.detected ?? "";
  const segments = detected ? highlightDifferences(detected) : [];
  const anyDifference = segments.some((segment) => segment.differs);

  return (
    <section className={`card result result--${field.verdict}`} aria-labelledby="warning-heading">
      <div className="result__head">
        <h3 id="warning-heading">Government warning</h3>
        <VerdictBadge verdict={field.verdict} />
      </div>

      <div className="warning-block">
        <div>
          <p className="micro-label">Detected on label</p>
          <p className="warning-text">
            {detected ? (
              segments.map((segment, index) =>
                segment.differs ? (
                  <mark key={index}>{segment.text} </mark>
                ) : (
                  <span key={index}>{segment.text} </span>
                ),
              )
            ) : (
              <span>No government warning was found on this label.</span>
            )}
          </p>
          <p style={{ margin: "12px 0 0" }}>
            {detected && !anyDifference
              ? "Nothing is highlighted, because the wording matches the required text exactly. "
              : detected
                ? "The highlighted words differ from the text required by 27 CFR 16.21. "
                : ""}
            {field.reason}
          </p>
        </div>
        <EvidenceCrop src={field.crop_url} fieldName="government_warning" detected={!!field.detected} tall />
      </div>

      <hr className="result__divider" />

      <h4 className="micro-label">Each rule, checked separately</h4>
      <div className="stack" style={{ gap: 10 }}>
        {checks.map((check) => (
          <div key={check.check} className={`subcheck subcheck--${check.verdict}`}>
            <VerdictBadge verdict={check.verdict} small />
            <span className="subcheck__name">{check.display_name}</span>
            <span className="subcheck__reason">{check.reason}</span>
          </div>
        ))}
      </div>

    </section>
  );
}
