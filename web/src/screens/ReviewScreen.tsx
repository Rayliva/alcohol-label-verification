import { useEffect, useState } from "react";

import { ApiError, fetchQueueItem, labelImageUrl, recordDecision } from "../api/client";
import type { QueueItemDetail } from "../api/types";
import { ResultsScreen } from "./ResultsScreen";

/**
 * One application, opened from the queue.
 *
 * The verdict was computed before the agent arrived, so nothing is recomputed
 * here — the same results screen an upload produces, with the artwork and a
 * decision beside it.
 */

type Action = "approve" | "reject" | "override";

const ACTIONS: { action: Action; label: string; hint: string }[] = [
  { action: "approve", label: "Approve", hint: "The label matches the application." },
  { action: "reject", label: "Reject", hint: "Send this back to the applicant." },
  {
    action: "override",
    label: "Approve with a note",
    hint: "The tool flagged something you have judged acceptable.",
  },
];

export function ReviewScreen({
  id,
  onBack,
  onDecided,
}: {
  id: string;
  onBack: () => void;
  onDecided: () => void;
}) {
  const [item, setItem] = useState<QueueItemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState<Action | null>(null);

  useEffect(() => {
    let live = true;
    fetchQueueItem(id)
      .then((data) => live && setItem(data))
      .catch(
        (cause) =>
          live &&
          setError(
            cause instanceof ApiError
              ? cause.body.message
              : "Can't load this application right now.",
          ),
      );
    return () => {
      live = false;
    };
  }, [id]);

  const decide = async (action: Action) => {
    setSaving(action);
    try {
      await recordDecision(id, action, note);
      onDecided();
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.body.message : "Could not save that decision.",
      );
      setSaving(null);
    }
  };

  if (error) {
    return (
      <section className="notice notice--error" role="alert">
        <h2>{error}</h2>
        <button className="button" type="button" onClick={onBack}>
          Back to the queue
        </button>
      </section>
    );
  }

  if (!item) {
    return (
      <section className="card">
        <p className="help">Loading this application…</p>
      </section>
    );
  }

  return (
    <>
      <button className="button button--quiet" type="button" onClick={onBack}>
        ← Back to the queue
      </button>

      {item.has_image ? (
        <section className="card">
          <h2>The label as submitted</h2>
          <img
            className="review__artwork"
            src={labelImageUrl(item.id)}
            alt={`Submitted label artwork for ${item.brand}`}
          />
        </section>
      ) : null}

      {item.unreadable ? (
        <section className="notice notice--warn">
          <h2>{item.unreadable.message}</h2>
          <p style={{ marginBottom: 0 }}>{item.unreadable.what_to_do}</p>
        </section>
      ) : null}

      {item.result ? (
        <ResultsScreen
          response={item.result}
          reviewer={item.decision?.decided_by ?? ""}
          onCheckAnother={onBack}
        />
      ) : null}

      <section className="card">
        <h2>Your decision</h2>
        {item.decision ? (
          <p className="help">
            Already {item.decision.action}d by {item.decision.decided_by}.
            {item.decision.note ? ` Note: ${item.decision.note}` : ""}
          </p>
        ) : (
          <>
            <label className="field">
              <span className="field__label">Note (optional)</span>
              <textarea
                className="textarea"
                rows={3}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
              <span className="help">
                Anything the next person reading this application should know.
              </span>
            </label>
            <div className="review__actions">
              {ACTIONS.map(({ action, label, hint }) => (
                <div key={action} className="review__action">
                  <button
                    className={`button${action === "approve" ? " button--primary" : ""}`}
                    type="button"
                    disabled={saving !== null}
                    onClick={() => decide(action)}
                  >
                    {saving === action ? "Saving…" : label}
                  </button>
                  <span className="help">{hint}</span>
                </div>
              ))}
            </div>
            <p className="help" style={{ marginTop: 16 }}>
              Decisions are kept for this session only. Nothing about an
              application is stored, so a restart clears them.
            </p>
          </>
        )}
      </section>
    </>
  );
}
