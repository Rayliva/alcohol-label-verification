import { useMemo } from "react";

import type { VerificationResponse, Verdict } from "../api/types";
import { FieldResultCard } from "../components/FieldResultCard";
import { verdictGlyph } from "../components/VerdictBadge";
import { WarningBlock } from "../components/WarningBlock";

/**
 * Screen 3: the field-by-field result.
 *
 * Sorted problems first. An agent should never hunt for the failure; that is a
 * stated requirement, not a preference.
 */

const SEVERITY: Record<Verdict, number> = { fail: 0, needs_review: 1, pass: 2 };

function headline(response: VerificationResponse): string {
  if (response.overall === "unreadable") return "This label could not be read";
  const issues = response.fields.filter((field) => field.verdict !== "pass").length;
  if (issues === 0) return "Everything on this label matches the application";
  // The outcome is a word, not just a count: without it, one flagged field
  // and one failing field both read "1 issue found", identical to a screen
  // reader since the glyph is aria-hidden, and different only by colour to
  // everyone else (rule 5).
  const outcome = response.overall === "fail" ? "This label fails." : "This label needs review.";
  return `${issues} ${issues === 1 ? "issue" : "issues"} found. ${outcome}`;
}

function toCsv(response: VerificationResponse): string {
  const rows = [
    ["field", "declared", "detected", "verdict", "confidence", "reason"],
    ...response.fields.map((field) => [
      field.field,
      field.declared ?? "",
      field.detected ?? "",
      field.verdict,
      String(field.confidence),
      field.reason,
    ]),
  ];
  return rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(",")).join("\n");
}

export function ResultsScreen({
  response,
  reviewer,
  onCheckAnother,
  /** True when this sits inside the review screen, which owns the page's one
   * dominant action and its own back button. */
  embedded = false,
}: {
  response: VerificationResponse;
  reviewer: string;
  onCheckAnother: () => void;
  embedded?: boolean;
}) {
  const ordered = useMemo(
    () =>
      [...response.fields]
        .filter((field) => field.field !== "government_warning")
        .sort((left, right) => SEVERITY[left.verdict] - SEVERITY[right.verdict]),
    [response.fields],
  );
  const warning = response.fields.find((field) => field.field === "government_warning");
  const counts = response.counts ?? {};

  const download = () => {
    const blob = new Blob([toCsv(response)], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${response.label_id || "label"}-results.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="stack">
      <section className={`summary summary--${response.overall}`} aria-labelledby="summary-heading">
        <span className="summary__glyph" aria-hidden="true">
          {verdictGlyph(response.overall)}
        </span>
        <div>
          <h1 id="summary-heading">{headline(response)}</h1>
          {response.overall === "unreadable" ? null : (
            <p className="summary__counts">
              {counts.pass ?? 0} {(counts.pass ?? 0) === 1 ? "field passes" : "fields pass"} ·{" "}
              {counts.needs_review ?? 0} {(counts.needs_review ?? 0) === 1 ? "needs" : "need"}{" "}
              review · {counts.fail ?? 0} {(counts.fail ?? 0) === 1 ? "fails" : "fail"}
            </p>
          )}
          {response.label_id || reviewer ? (
            <p className="summary__meta">
              {response.label_id ? `Application ${response.label_id}` : ""}
              {response.label_id && reviewer ? " · " : ""}
              {reviewer ? `Reviewed by ${reviewer}` : ""}
            </p>
          ) : null}
        </div>
        <div className="summary__actions">
          <button type="button" className="button" onClick={download}>
            Export results (CSV)
          </button>
          {embedded ? null : (
            <button type="button" className="button button--primary" onClick={onCheckAnother}>
              Back to the queue
            </button>
          )}
        </div>
      </section>

      {response.error ? (
        <section className="notice notice--error" aria-labelledby="error-heading">
          <h2 id="error-heading">{response.error.message}</h2>
          <p style={{ marginBottom: 0 }}>{response.error.what_to_do}</p>
        </section>
      ) : null}

      <div className="results-grid">
      {ordered.map((field) => (
        <FieldResultCard key={field.field} field={field} />
      ))}
      </div>

      {warning ? <WarningBlock field={warning} checks={response.warning_checks} /> : null}
    </div>
  );
}
