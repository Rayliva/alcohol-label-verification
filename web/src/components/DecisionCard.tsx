import { useState } from "react";

import { ApiError, recordDecision } from "../api/client";

/**
 * Approve or reject one application, with an optional note.
 *
 * One card, two homes: the review screen, and the results screen right after
 * an upload, so an agent who just watched the check finish can decide on the
 * spot instead of finding the same application again in the queue.
 *
 * Approving a flagged application is recorded as an override; that is
 * inferred from the verdict rather than offered as a third button.
 */

type Action = "approve" | "reject" | "override";

export function DecisionCard({
  queueId,
  flagged,
  onDecided,
}: {
  queueId: string;
  flagged: boolean;
  /** Called with the next undecided application's id, or null when the
   * queue is done — the caller decides where that leads. */
  onDecided: (nextId: string | null) => void;
}) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);

  const decide = async (action: Action) => {
    setSaving(action);
    setError(null);
    try {
      const { nextId } = await recordDecision(queueId, action, note);
      onDecided(nextId);
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.body.message : "Could not save that decision.",
      );
      setSaving(null);
    }
  };

  return (
    <section className="card" aria-labelledby={`decision-${queueId}`}>
      <h2 id={`decision-${queueId}`}>Your decision</h2>
      {error ? (
        <p className="blocked" role="alert">
          {error} Try again in a moment.
        </p>
      ) : null}
      <label className="field">
        <span className="field__label">Note (optional)</span>
        <textarea
          className="textarea"
          rows={2}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>
      <div className="review__actions">
        <button
          className="button button--primary"
          type="button"
          disabled={saving !== null}
          onClick={() => decide(flagged ? "override" : "approve")}
        >
          {saving === "approve" || saving === "override"
            ? "Saving…"
            : "Approve this application"}
        </button>
        <button
          className="button button--danger"
          type="button"
          disabled={saving !== null}
          onClick={() => decide("reject")}
        >
          {saving === "reject" ? "Saving…" : "Reject this application"}
        </button>
      </div>
    </section>
  );
}
