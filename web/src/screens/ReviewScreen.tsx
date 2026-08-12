import { useEffect, useState } from "react";

import { ApiError, fetchQueueItem, labelImageUrl, recordDecision } from "../api/client";
import type { QueueItemDetail } from "../api/types";
import { Lightbox } from "../components/Lightbox";
import { ResultsScreen } from "./ResultsScreen";

/**
 * One application, opened from the queue.
 *
 * The verdict was computed before the agent arrived, so nothing is recomputed
 * here. It is the same results screen an upload produces, with the artwork and a
 * decision beside it.
 */

type Action = "approve" | "reject" | "override";

/** How a recorded decision reads back. "Overrided" is not a word. */
export const DECISION_LABEL: Record<Action, string> = {
  approve: "Approved",
  reject: "Rejected",
  override: "Approved over the flags",
};

export function ReviewScreen({
  id,
  onBack,
  onDecided,
  /** True when this application opened as part of a reviewing run, where a
   * decision flows into the next undecided application. The banner exists
   * because of that flow: the screen changes under the agent, so it has to
   * say whose application it is showing. */
  queueRun = false,
}: {
  id: string;
  onBack: () => void;
  /** Called with the next undecided application's id, or null when the
   * queue is done — the caller decides where that leads. */
  onDecided: (nextId: string | null) => void;
  queueRun?: boolean;
}) {
  const [item, setItem] = useState<QueueItemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState<Action | null>(null);
  const [artworkOpen, setArtworkOpen] = useState(false);

  useEffect(() => {
    let live = true;
    // A new application starts fresh: no leftover note, no disabled buttons,
    // and the page back at the top — in a run the previous application left
    // the scroll at its decision buttons, which is exactly where a new one
    // would be mistaken for the old.
    setItem(null);
    setNote("");
    setSaving(null);
    setError(null);
    setArtworkOpen(false);
    window.scrollTo(0, 0);
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
      const { nextId } = await recordDecision(id, action, note);
      onDecided(nextId);
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.body.message : "Could not save that decision.",
      );
      setSaving(null);
    }
  };

  // One persistent node across loading and loaded states, so the change of
  // application is announced by the live region rather than left to be
  // noticed.
  const banner = queueRun ? (
    <p className="run-banner" role="status">
      {item ? (
        <>
          Now reviewing <strong>{item.brand}</strong>. Deciding opens the next
          application in the queue.
        </>
      ) : (
        "Opening the next application…"
      )}
    </p>
  ) : null;

  if (error) {
    return (
      <>
        {banner}
        <section className="notice notice--error" role="alert">
          <h2>{error}</h2>
          <button className="button" type="button" onClick={onBack}>
            Back to the queue
          </button>
        </section>
      </>
    );
  }

  if (!item) {
    return (
      <>
        {banner}
        <section className="card">
          <p className="help">Loading this application…</p>
        </section>
      </>
    );
  }

  const flagged = item.outcome !== "pass";

  return (
    <>
      {banner}
      <button className="back-link" type="button" onClick={onBack}>
        <span aria-hidden="true">←</span> Back to the queue
      </button>

      {item.has_image ? (
        <section className="card">
          <h2>The label as submitted</h2>
          <button
            type="button"
            className="review__artwork-button"
            onClick={() => setArtworkOpen(true)}
          >
            <img
              className="review__artwork"
              src={labelImageUrl(item.id)}
              alt={`Submitted label artwork for ${item.brand}`}
            />
            <span className="visually-hidden">Click to enlarge</span>
          </button>
          {artworkOpen ? (
            <Lightbox
              src={labelImageUrl(item.id)}
              alt={`Submitted label artwork for ${item.brand}`}
              onClose={() => setArtworkOpen(false)}
            />
          ) : null}
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
          embedded
        />
      ) : null}

      <section className="card">
        <h2>Your decision</h2>
        {item.decision ? (
          <p className="help">
            {DECISION_LABEL[item.decision.action]} by {item.decision.decided_by}.
            {item.decision.note ? ` Note: ${item.decision.note}` : ""}
          </p>
        ) : (
          <>
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
          </>
        )}
      </section>
    </>
  );
}
