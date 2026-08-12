import { useEffect, useState } from "react";

import { ApiError, fetchQueue } from "../api/client";
import type { QueueListing, QueueRow } from "../api/types";
import { VerdictBadge, verdictWord } from "../components/VerdictBadge";
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

type DecidedFilter = "all" | "undecided" | "decided";
type OutcomeFilter = "all" | "needs_review" | "unreadable" | "fail" | "pass";

export function QueueScreen({
  onOpen,
  onStart,
  reloadKey,
}: {
  onOpen: (id: string) => void;
  /** Begin a reviewing run at the given application, the queue's first
   * undecided one. */
  onStart: (id: string) => void;
  reloadKey: number;
}) {
  const [listing, setListing] = useState<QueueListing | null>(null);
  const [query, setQuery] = useState("");
  const [decidedFilter, setDecidedFilter] = useState<DecidedFilter>("all");
  const [outcomeFilter, setOutcomeFilter] = useState<OutcomeFilter>("all");
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

  const needle = query.trim().toLowerCase();
  const shown = listing.items.filter((row: QueueRow) => {
    const matchesText =
      !needle ||
      row.brand.toLowerCase().includes(needle) ||
      row.id.toLowerCase().includes(needle) ||
      Boolean(row.application_id?.toLowerCase().includes(needle));
    const matchesState =
      decidedFilter === "all" || (decidedFilter === "decided") === Boolean(row.decision);
    const matchesOutcome = outcomeFilter === "all" || row.outcome === outcomeFilter;
    return matchesText && matchesState && matchesOutcome;
  });

  const firstUndecided = listing.items.find((row: QueueRow) => !row.decision);

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
        {firstUndecided ? (
          <button
            type="button"
            className="button button--primary"
            onClick={() => onStart(firstUndecided.id)}
          >
            Start reviewing
          </button>
        ) : null}
      </div>

      <div className="queue-controls">
        <div className="field queue-controls__search">
          <label className="field__label" htmlFor="queue-search">
            Search
          </label>
          <input
            id="queue-search"
            className="input"
            type="search"
            placeholder="Brand or application ID"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="field">
          <label className="field__label" htmlFor="queue-decided">
            Decision
          </label>
          <select
            id="queue-decided"
            className="select"
            value={decidedFilter}
            onChange={(event) => setDecidedFilter(event.target.value as DecidedFilter)}
          >
            <option value="all">All</option>
            <option value="undecided">Not decided</option>
            <option value="decided">Decided</option>
          </select>
        </div>
        <div className="field">
          <label className="field__label" htmlFor="queue-outcome">
            Result
          </label>
          <select
            id="queue-outcome"
            className="select"
            value={outcomeFilter}
            onChange={(event) => setOutcomeFilter(event.target.value as OutcomeFilter)}
          >
            <option value="all">All</option>
            <option value="needs_review">Needs review</option>
            <option value="unreadable">Could not be read</option>
            <option value="fail">Fail</option>
            <option value="pass">Pass</option>
          </select>
        </div>
      </div>

      {shown.length === 0 ? (
        <p className="help" role="status">
          No applications match. Clear the search or choose another filter to
          see all {listing.items.length}.
        </p>
      ) : (
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
          {shown.map((row: QueueRow) => (
            <tr key={row.id} className={row.decision ? "queue__row--decided" : undefined}>
              <th scope="row" className="queue__brand">
                {row.brand}
                {row.application_id || row.source === "uploaded" ? (
                  <span className="queue__tag">
                    {row.application_id ? `Application ${row.application_id}` : ""}
                    {row.application_id && row.source === "uploaded" ? " · " : ""}
                    {row.source === "uploaded" ? "Uploaded by you" : ""}
                  </span>
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
                  <span className="visually-hidden">, {verdictWord(row.outcome)}</span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      )}
    </section>
  );
}
