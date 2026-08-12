import { useState } from "react";

import type { FieldOutcome } from "../api/types";
import { EvidenceCrop } from "./EvidenceCrop";
import { VerdictBadge } from "./VerdictBadge";

/**
 * One field's outcome, with the evidence beside it.
 *
 * Always visible: what the application declared, what was read off the label,
 * the region of the image it came from, and the verdict. The verdict badge
 * and its "Why?" disclosure sit together BELOW the evidence, so what the
 * disclosure expands is visibly attached to the verdict it explains.
 *
 * The prose behind the disclosure — reason, reading confidence, rule
 * citation — is a deliberate deviation from accessibility rule 5 ("no
 * important content behind disclosure"), decided by the product owner on
 * 2026-08-11: six cards of rationale crowded out the results themselves.
 *
 * There are no per-field decision controls. The tool advises field by field;
 * the agent decides once, per application, with Approve and Reject on the
 * review screen (product owner, 2026-08-11 — the per-field accept/reject
 * asked the same question up to seven times per label).
 */

function confidenceWord(confidence: number): string {
  if (confidence >= 0.95) return "high";
  if (confidence >= 0.85) return "good";
  return "low, look closely";
}

export function FieldResultCard({ field }: { field: FieldOutcome }) {
  const [open, setOpen] = useState(false);

  return (
    <section
      className={`card result result--${field.verdict}`}
      aria-labelledby={`field-${field.field}`}
    >
      <div className="result__head">
        <h3 id={`field-${field.field}`}>{field.display_name}</h3>
      </div>

      <div className="result__values">
        <div>
          <p className="micro-label">Declared in application</p>
          <p className="mono">{field.declared || "nothing declared"}</p>
        </div>
        <div>
          <p className="micro-label">Detected on label</p>
          <p className="mono">{field.detected || "not found on the label"}</p>
        </div>
        <EvidenceCrop src={field.crop_url} fieldName={field.field} detected={!!field.detected} />
      </div>

      <div className="result__verdict">
        <VerdictBadge verdict={field.verdict} />
        <button
          type="button"
          className="button button--small result__why"
          aria-expanded={open}
          aria-controls={`why-${field.field}`}
          onClick={() => setOpen((state) => !state)}
        >
          <span aria-hidden="true">{open ? "▲" : "▼"}</span> Why?
        </button>
      </div>

      {open ? (
        <div id={`why-${field.field}`} className="result__details">
          <p className="result__reason">{field.reason}</p>
          <p className="result__meta">
            Reading confidence {field.confidence.toFixed(2)} ({confidenceWord(field.confidence)})
            {field.citation ? ` · Rule: ${field.citation}` : ""}
          </p>
        </div>
      ) : null}
    </section>
  );
}
