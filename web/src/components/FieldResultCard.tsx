import { useState } from "react";

import type { FieldOutcome, Override } from "../api/types";
import { EvidenceCrop } from "./EvidenceCrop";
import { FieldDecision } from "./FieldDecision";
import { VerdictBadge } from "./VerdictBadge";

/**
 * One field's outcome, with the evidence beside it.
 *
 * Always visible: what the application declared, what was read off the label,
 * the region of the image it came from, and the verdict. The prose that
 * explains the verdict, the reading confidence, the rule citation, and the
 * agent's decision controls sit behind a "Why?" disclosure. That is a
 * deliberate deviation from accessibility rule 5 ("no important content
 * behind disclosure"), decided by the product owner on 2026-08-11: six cards
 * of rationale crowded out the results themselves. The verdict and the
 * evidence, the things an agent acts on, stay in the open.
 *
 * An override never replaces the tool's verdict. Both stay visible: the tool
 * advises, the agent decides, and the export needs to show both.
 */

function confidenceWord(confidence: number): string {
  if (confidence >= 0.95) return "high";
  if (confidence >= 0.85) return "good";
  return "low, look closely";
}

export function FieldResultCard({
  field,
  reviewer,
  override,
  onOverride,
}: {
  field: FieldOutcome;
  reviewer: string;
  override: Override | null;
  onOverride: (next: Override | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const rail = override ? "override" : field.verdict;

  return (
    <section className={`card result result--${rail}`} aria-labelledby={`field-${field.field}`}>
      <div className="result__head">
        <h3 id={`field-${field.field}`}>{field.display_name}</h3>
        {override ? (
          <span className="agent-mark">
            You: {override.decision === "accepted" ? "accepted" : "a problem"}
          </span>
        ) : null}
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

      {open ? (
        <div id={`why-${field.field}`} className="result__details">
          <p className="result__reason">{field.reason}</p>
          <p className="result__meta">
            Reading confidence {field.confidence.toFixed(2)} ({confidenceWord(field.confidence)})
            {field.citation ? ` · Rule: ${field.citation}` : ""}
          </p>
          <FieldDecision
            fieldKey={field.field}
            displayName={field.display_name}
            verdict={field.verdict}
            reviewer={reviewer}
            override={override}
            onOverride={onOverride}
          />
        </div>
      ) : null}
    </section>
  );
}
