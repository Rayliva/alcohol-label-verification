import type { FieldOutcome, Override } from "../api/types";
import { EvidenceCrop } from "./EvidenceCrop";
import { FieldDecision } from "./FieldDecision";
import { VerdictBadge } from "./VerdictBadge";

/**
 * One field's outcome, with the evidence beside it and, when the tool flagged
 * it, the agent's decision under it.
 *
 * Four things are visible at once and none of them is behind a control: what
 * the application declared, what was read off the label, the region of the
 * image it came from, and a plain sentence saying what to make of it.
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
        <EvidenceCrop src={field.crop_url} fieldName={field.field} />
      </div>

      <p className="result__reason">{field.reason}</p>
      <p className="result__meta">
        Reading confidence {field.confidence.toFixed(2)} ({confidenceWord(field.confidence)})
        {field.citation ? ` · Rule: ${field.citation}` : ""}
      </p>

      {field.verdict === "pass" ? null : (
        <FieldDecision
          fieldKey={field.field}
          displayName={field.display_name}
          verdict={field.verdict}
          reviewer={reviewer}
          override={override}
          onOverride={onOverride}
        />
      )}
    </section>
  );
}
