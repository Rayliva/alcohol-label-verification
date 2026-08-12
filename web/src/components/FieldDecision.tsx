import type { Override, Verdict } from "../api/types";

/**
 * The agent's call on one flagged field.
 *
 * Only flagged fields get this. A field the tool passed has nothing to
 * disagree with here; when an agent believes a passing application is wrong
 * anyway, the application-level Reject on the review screen is the recorded
 * disagreement (decided 2026-08-11, superseding the short-lived per-field
 * flag).
 *
 * What it does is stated on the control itself. These decisions travel with
 * the CSV export and nowhere else: nothing about an application is stored
 * (PRD C-2), so a claim that a note "goes on the record" would be false.
 */

export function FieldDecision({
  fieldKey,
  displayName,
  verdict,
  reviewer,
  override,
  onOverride,
}: {
  fieldKey: string;
  displayName: string;
  verdict: Verdict;
  reviewer: string;
  override: Override | null;
  onOverride: (next: Override | null) => void;
}) {
  const decide = (decision: "accepted" | "rejected") => {
    if (override?.decision === decision) {
      onOverride(null);
      return;
    }
    onOverride({
      decision,
      note: override?.note ?? "",
      at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    });
  };

  return (
    <div className="decision">
      <div className="decision__controls">
        <span className="decision__ask">
          The tool flagged this as {verdict.replace("_", " ")}. Do you agree?
        </span>
        <button
          type="button"
          className="button button--small"
          aria-pressed={override?.decision === "accepted"}
          onClick={() => decide("accepted")}
        >
          No, accept this field
        </button>
        <button
          type="button"
          className="button button--small button--danger"
          aria-pressed={override?.decision === "rejected"}
          onClick={() => decide("rejected")}
        >
          Yes, it is a problem
        </button>
        <label className="visually-hidden" htmlFor={`note-${fieldKey}`}>
          Note about {displayName}, optional
        </label>
        <input
          id={`note-${fieldKey}`}
          className="input input--small"
          placeholder="Note (optional)"
          value={override?.note ?? ""}
          disabled={!override}
          onChange={(event) =>
            override && onOverride({ ...override, note: event.target.value })
          }
        />
      </div>
      {override ? (
        <p className="decision__made">
          {override.decision === "accepted"
            ? "Accepted by you. The tool's verdict stays on the export beside your decision."
            : "Confirmed as a problem by you."}{" "}
          <span className="help">
            {reviewer ? `${reviewer}, ` : ""}
            {override.at}. Goes into the CSV export; nothing is stored after this session.
          </span>
        </p>
      ) : (
        <p className="help decision__hint">
          Pick one to enable the note. Both go into the CSV export.
        </p>
      )}
    </div>
  );
}
