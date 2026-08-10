import { useState } from "react";

import type { FieldOutcome, Override } from "../api/types";
import { EvidenceCrop } from "./EvidenceCrop";
import { VerdictBadge } from "./VerdictBadge";

/**
 * One field's outcome, with the evidence beside it and the agent's decision
 * under it.
 *
 * Four things are visible at once and none of them is behind a control: what
 * the application declared, what was read off the label, the region of the
 * image it came from, and a plain sentence saying what to make of it.
 *
 * An override never replaces the tool's verdict. Both stay on the record —
 * the tool advises, the agent decides, and an audit needs to see both.
 */

function confidenceWord(confidence: number): string {
  if (confidence >= 0.95) return "(high)";
  if (confidence >= 0.85) return "(good)";
  return "(low — look closely)";
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
  const [note, setNote] = useState(override?.note ?? "");
  const rail = override ? "override" : field.verdict;

  const decide = (decision: "accepted" | "rejected") => {
    if (override?.decision === decision) {
      onOverride(null);
      return;
    }
    onOverride({
      decision,
      note,
      at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    });
  };

  return (
    <section className={`card result result--${rail}`} aria-labelledby={`field-${field.field}`}>
      <div className="result__head">
        <h3 id={`field-${field.field}`}>{field.display_name}</h3>
        {override ? <VerdictBadge verdict="pass" small /> : null}
        <VerdictBadge verdict={field.verdict} />
      </div>

      <div className="result__values">
        <div>
          <p className="micro-label">Declared in application</p>
          <p className="mono">{field.declared || "— nothing declared —"}</p>
        </div>
        <div>
          <p className="micro-label">Detected on label</p>
          <p className="mono">{field.detected || "— not found on the label —"}</p>
        </div>
        <EvidenceCrop src={field.crop_url} fieldName={field.field} />
      </div>

      <hr className="result__divider" />

      <p style={{ margin: 0 }}>{field.reason}</p>
      <div className="confidence">
        <span>Reading confidence {field.confidence.toFixed(2)}</span>
        <span className="confidence__track" aria-hidden="true">
          <span
            className="confidence__fill"
            style={{ width: `${Math.round(field.confidence * 100)}%`, display: "block" }}
          />
        </span>
        <span>{confidenceWord(field.confidence)}</span>
      </div>
      {field.citation ? <p className="help">Rule: {field.citation}</p> : null}

      <hr className="result__divider" />

      {override ? (
        <div className="override-panel">
          <p style={{ margin: 0, fontWeight: 700 }}>
            Agent decision: {override.decision === "accepted" ? "Accepted" : "Rejected"}
          </p>
          <p style={{ margin: "6px 0 0" }}>
            The tool&apos;s original verdict was <strong>{field.verdict.replace("_", " ")}</strong>.
            It has been kept on the record alongside your decision.
          </p>
          <p className="help">
            Decided {reviewer ? `by ${reviewer} ` : ""}at {override.at}
            {override.note ? ` — “${override.note}”` : ""}
          </p>
        </div>
      ) : null}

      <div className="override-controls">
        <button
          type="button"
          className="button"
          aria-pressed={override?.decision === "accepted"}
          onClick={() => decide("accepted")}
        >
          Accept this field
        </button>
        <button
          type="button"
          className="button button--danger"
          aria-pressed={override?.decision === "rejected"}
          onClick={() => decide("rejected")}
        >
          Reject this field
        </button>
        <label className="visually-hidden" htmlFor={`note-${field.field}`}>
          Note about {field.display_name}, optional — goes on the record
        </label>
        <input
          id={`note-${field.field}`}
          className="input"
          placeholder="Note (optional) — goes on the record"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
    </section>
  );
}
