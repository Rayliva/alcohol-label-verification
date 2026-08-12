import { useMemo, useState } from "react";

import type { Override, VerificationResponse, Verdict } from "../api/types";
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
  return `${issues} ${issues === 1 ? "issue" : "issues"} found on this label`;
}

function toCsv(response: VerificationResponse, overrides: Record<string, Override>): string {
  const rows = [
    ["field", "declared", "detected", "verdict", "confidence", "reason", "agent_decision", "note"],
    ...response.fields.map((field) => [
      field.field,
      field.declared ?? "",
      field.detected ?? "",
      field.verdict,
      String(field.confidence),
      field.reason,
      overrides[field.field]?.decision ?? "",
      overrides[field.field]?.note ?? "",
    ]),
  ];
  return rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(",")).join("\n");
}

export function ResultsScreen({
  response,
  reviewer,
  onCheckAnother,
  /** True when this sits inside the review screen, which owns the page's one
   * dominant action and its own back button. It also means the verdict was
   * read back from a recording, so the elapsed time belongs to the machine
   * that recorded it rather than to anything the agent just waited for. */
  embedded = false,
}: {
  response: VerificationResponse;
  reviewer: string;
  onCheckAnother: () => void;
  embedded?: boolean;
}) {
  const [overrides, setOverrides] = useState<Record<string, Override>>({});

  const ordered = useMemo(
    () =>
      [...response.fields]
        .filter((field) => field.field !== "government_warning")
        .sort((left, right) => SEVERITY[left.verdict] - SEVERITY[right.verdict]),
    [response.fields],
  );
  const warning = response.fields.find((field) => field.field === "government_warning");

  const counts = response.counts ?? {};
  const seconds = (response.processing_ms / 1000).toFixed(1);

  const download = () => {
    const blob = new Blob([toCsv(response, overrides)], { type: "text/csv" });
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
              {counts.pass ?? 0} fields pass · {counts.needs_review ?? 0} need review ·{" "}
              {counts.fail ?? 0} fail
            </p>
          )}
          <p className="summary__meta">
            {response.label_id ? `Application ${response.label_id} · ` : ""}
            {response.beverage_type}
            {embedded ? "" : ` · read in ${seconds} seconds`}
            {reviewer ? ` · reviewed by ${reviewer}` : ""}
          </p>
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
        <FieldResultCard
          key={field.field}
          field={field}
          reviewer={reviewer}
          override={overrides[field.field] ?? null}
          onOverride={(next) =>
            setOverrides((current) => {
              const copy = { ...current };
              if (next) copy[field.field] = next;
              else delete copy[field.field];
              return copy;
            })
          }
        />
      ))}
      </div>

      {warning ? (
        <WarningBlock
          field={warning}
          checks={response.warning_checks}
          reviewer={reviewer}
          override={overrides.government_warning ?? null}
          onOverride={(next) =>
            setOverrides((current) => {
              const copy = { ...current };
              if (next) copy.government_warning = next;
              else delete copy.government_warning;
              return copy;
            })
          }
        />
      ) : null}
    </div>
  );
}
