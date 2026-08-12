import type { Override, Verdict } from "../api/types";

/**
 * The agent's call on one field.
 *
 * On a flagged field the question is "do you agree?", with both answers
 * offered. On a passing field the only meaningful action is disagreement, so
 * that is the only control: flag it as a problem the tool missed.
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

  const passed = verdict === "pass";

  return (
    <div className="decision">
      <div className="decision__controls">
        <span className="decision__ask">
          {passed
            ? "Spotted a problem the tool missed?"
            : `The tool flagged this as ${verdict.replace("_", " ")}. Do you agree?`}
        </span>
        {passed ? null : (
          <button
            type="button"
            className="button button--small"
            aria-pressed={override?.decision === "accepted"}
            onClick={() => decide("accepted")}
          >
            No, accept this field
          </button>
        )}
        <button
          type="button"
          className="button button--small button--danger"
          aria-pressed={override?.decision === "rejected"}
          onClick={() => decide("rejected")}
        >
          {passed ? "Flag as a problem" : "Yes, it is a problem"}
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
            : "Flagged as a problem by you. The tool's verdict stays on the export beside your decision."}{" "}
          <span className="help">
            {reviewer ? `${reviewer}, ` : ""}
            {override.at}. Goes into the CSV export; nothing is stored after this session.
          </span>
        </p>
      ) : (
        <p className="help decision__hint">
          {passed
            ? "Flagging enables the note. Both go into the CSV export."
            : "Pick one to enable the note. Both go into the CSV export."}
        </p>
      )}
    </div>
  );
}
