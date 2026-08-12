import { useEffect, useState } from "react";

import { ApiError, fetchQueue } from "../api/client";
import type { QueueListing, QueueRow } from "../api/types";
import { VerdictBadge } from "../components/VerdictBadge";
import { DECISION_LABEL } from "./ReviewScreen";

/**
 * What an agent sees when they sign in.
 *
 * The brief describes an agent pulling up an application that is already
 * waiting, not keying one in, so this is the front door, and the verdicts are
 * already computed by the time a row appears.
 *
 * Rows sort judgment-first. A NEEDS_REVIEW is the work only a person can do; a
 * FAIL the tool is confident about still needs signing off but is not where an
 * agent's attention is scarcest. Anything already decided drops to the bottom.
 *
 * No timings here. These verdicts were recorded rather than computed on demand,
 * so a stopwatch beside them would be reporting the machine that made the
 * recording. The five-second budget is demonstrated where it is actually spent,
 * on the upload screen.
 */

const OUTCOME_LABEL: Record<string, string> = {
  needs_review: "Needs review",
  unreadable: "Could not be read",
  fail: "Fail",
  pass: "Pass",
};

export function QueueScreen({
  onOpen,
  reloadKey,
}: {
  onOpen: (id: string) => void;
  reloadKey: number;
}) {
  const [listing, setListing] = useState<QueueListing | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetchQueue()
      .then((data) => live && setListing(data))
      .catch((cause) =>
        live &&
        setError(
          cause instanceof ApiError
            ? cause.body.message
            : "Can't load the review queue right now.",
        ),
      );
    return () => {
      live = false;
    };
  }, [reloadKey]);

  if (error) {
    return (
      <section className="notice notice--error" role="alert">
        <h2>{error}</h2>
        <p style={{ marginBottom: 0 }}>Reload the page to try again.</p>
      </section>
    );
  }

  if (!listing) {
    return (
      <section className="card">
        <h1>Applications to review</h1>
        <p className="help">Loading the queue…</p>
      </section>
    );
  }

  const waiting = listing.awaiting_decision;

  return (
    <section className="card">
      <div className="queue__head">
        <div>
          <h1>Applications to review</h1>
          <p className="help" style={{ marginBottom: 0 }}>
            {waiting === 0
              ? "Every application here has been decided."
              : `${waiting} of ${listing.items.length} still need a decision. Those needing judgment are listed first.`}
          </p>
        </div>
      </div>

      <table className="queue">
        <caption className="visually-hidden">
          Applications awaiting review, those needing human judgment first
        </caption>
        <thead>
          <tr>
            <th scope="col">Brand</th>
            <th scope="col">Result</th>
            <th scope="col">Decision</th>
            <th scope="col">
              <span className="visually-hidden">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {listing.items.map((row: QueueRow) => (
            <tr key={row.id} className={row.decision ? "queue__row--decided" : undefined}>
              <th scope="row" className="queue__brand">
                {row.brand}
                {row.source === "uploaded" ? (
                  <span className="queue__tag">Uploaded by you</span>
                ) : null}
              </th>
              <td>
                <VerdictBadge verdict={row.outcome} small />
              </td>
              <td>
                {row.decision ? (
                  <span className="queue__decision">
                    {DECISION_LABEL[row.decision.action]}
                  </span>
                ) : (
                  <span className="queue__decision queue__decision--none">
                    Not yet decided
                  </span>
                )}
              </td>
              <td>
                <button
                  className="button"
                  type="button"
                  onClick={() => onOpen(row.id)}
                >
                  Review {row.brand}
                  <span className="visually-hidden">
                    , {OUTCOME_LABEL[row.outcome] ?? row.outcome}
                  </span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
