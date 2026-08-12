import { useEffect, useRef, useState } from "react";

import {
  batchProgress,
  exportUrl,
  preflight,
  startBatch,
  stopBatch,
  templateUrl,
} from "../api/batch";
import type { BatchProgress, PreflightReport } from "../api/batch";
import { ApiError } from "../api/client";
import type { ErrorBody, Outcome } from "../api/types";
import { VerdictBadge } from "../components/VerdictBadge";

/**
 * Screens 4-6: upload, progress, results table.
 *
 * Peak season sends 200-300 applications at once. Three things make that
 * survivable and all three are non-negotiable: every mismatch is named before
 * the run starts, progress is determinate throughout, and the results table is
 * sorted problems-first so nobody hunts for the failures.
 */

type Filter = "all" | "fail" | "needs_review" | "pass" | "unreadable" | "error";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "fail", label: "Failures" },
  { key: "needs_review", label: "Need review" },
  { key: "pass", label: "Passed" },
  { key: "unreadable", label: "Could not be read" },
  { key: "error", label: "Could not be checked" },
];

const ORDER: Record<string, number> = {
  fail: 0,
  unreadable: 1,
  error: 2,
  needs_review: 3,
  pass: 4,
};

function minutes(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} seconds`;
  return `${Math.round(seconds / 60)} minutes`;
}

export function BatchScreen() {
  const [images, setImages] = useState<File[]>([]);
  const [manifest, setManifest] = useState<File | null>(null);
  const [report, setReport] = useState<PreflightReport | null>(null);
  const [job, setJob] = useState<BatchProgress | null>(null);
  const [error, setError] = useState<ErrorBody | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const imageInput = useRef<HTMLInputElement>(null);
  const manifestInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!images.length || !manifest) {
      setReport(null);
      return;
    }
    let cancelled = false;
    setReport(null);
    preflight(images, manifest)
      .then((next) => {
        if (!cancelled) {
          setReport(next);
          setError(null);
        }
      })
      .catch((cause) => {
        if (cancelled) return;
        // A rejected manifest must not leave the previous summary on screen
        // with its button still armed, and it would submit the file that was
        // just refused.
        setReport(null);
        setError(cause instanceof ApiError ? cause.body : null);
      });
    return () => {
      cancelled = true;
    };
  }, [images, manifest]);

  useEffect(() => {
    if (!job || job.state === "finished" || job.state === "stopped") return;
    const timer = window.setInterval(() => {
      batchProgress(job.job_id).then(setJob).catch(() => undefined);
    }, 700);
    return () => window.clearInterval(timer);
  }, [job]);

  const begin = async () => {
    if (!manifest || !report?.ready) return;
    try {
      const started = await startBatch(images, manifest);
      setJob(await batchProgress(started.job_id));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.body : null);
    }
  };

  const results = job
    ? [...job.results]
        .sort((left, right) => (ORDER[left.outcome] ?? 9) - (ORDER[right.outcome] ?? 9))
        .filter((row) => filter === "all" || row.outcome === filter)
    : [];

  const countFor = (key: Filter) =>
    key === "all" ? (job?.done ?? 0) : (job?.counts?.[key] ?? 0);

  return (
    <div className="stack">
      {error ? (
        <section className="notice notice--error">
          <h2>{error.message}</h2>
          <p style={{ marginBottom: 0 }}>{error.what_to_do}</p>
        </section>
      ) : null}

      {!job ? (
        <>
          <section className="card" aria-labelledby="images-heading">
            <h2 id="images-heading">The label artwork</h2>
            <p className="help">Every label image for this batch, selected at once. JPG or PNG.</p>
            <div className="file-picker">
              <button
                type="button"
                className="button"
                onClick={() => imageInput.current?.click()}
              >
                Choose image files
              </button>
              <span className="file-status">{images.length} images selected</span>
              {images.length ? (
                <button type="button" className="button" onClick={() => setImages([])}>
                  Clear all
                </button>
              ) : null}
            </div>
            <label className="visually-hidden" htmlFor="batch-images">
              Label image files
            </label>
            <input
              ref={imageInput}
              id="batch-images"
              className="visually-hidden"
              type="file"
              multiple
              accept="image/png,image/jpeg"
              onChange={(event) => {
                // Reset after reading, or picking the same files again fires
                // no change event and the screen looks like it ignored you.
                setImages(Array.from(event.target.files ?? []));
                event.target.value = "";
              }}
            />
          </section>

          <section className="card" aria-labelledby="manifest-heading">
            <h2 id="manifest-heading">What the applications say</h2>
            <p className="help">
              A spreadsheet, one row per application, naming the image file it
              belongs to. CSV or JSON.
            </p>
            <div className="file-picker">
              <button
                type="button"
                className="button"
                onClick={() => manifestInput.current?.click()}
              >
                Choose spreadsheet
              </button>
              <span className="file-status">{manifest ? manifest.name : "none chosen yet"}</span>
            </div>
            <label className="visually-hidden" htmlFor="batch-manifest">
              Application spreadsheet
            </label>
            <input
              ref={manifestInput}
              id="batch-manifest"
              className="visually-hidden"
              type="file"
              accept=".csv,.json,text/csv,application/json"
              onChange={(event) => {
                setManifest(event.target.files?.[0] ?? null);
                event.target.value = "";
              }}
            />
            <p className="help" style={{ marginTop: 10 }}>
              Not sure of the column names?{" "}
              <a href={templateUrl} download>
                Download the template spreadsheet (CSV)
              </a>
              .
            </p>
          </section>

          {images.length && manifest ? (
          <section className="card" aria-labelledby="preflight-heading">
            <h2 id="preflight-heading">Before we start</h2>
            {report ? (
              <>
                <p style={{ fontSize: "var(--size-h3)" }}>
                  {report.image_count} images · {report.row_count} spreadsheet rows ·{" "}
                  <strong>{report.matched_count} matched</strong>
                  {report.problem_count ? ` · ${report.problem_count} need attention` : ""}
                </p>
                {report.problems.length ? (
                  <div className="notice notice--warn" style={{ marginTop: 12 }}>
                    <p style={{ margin: "0 0 8px", fontWeight: 700 }}>
                      These will be skipped:
                    </p>
                    <ul style={{ margin: 0, paddingLeft: 22 }}>
                      {report.problems.map((problem) => (
                        <li key={problem.detail}>{problem.detail}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <hr className="result__divider" />
                {report.ready ? (
                  <p className="ready">Ready to check.</p>
                ) : (
                  <p className="blocked">
                    No spreadsheet row matched an uploaded image, so there is nothing to check.
                  </p>
                )}
                <button
                  type="button"
                  className="button button--primary button--wide"
                  disabled={!report.ready}
                  onClick={begin}
                >
                  Check these {report.matched_count} labels
                </button>
              </>
            ) : (
              <p className="help">Checking your files…</p>
            )}
          </section>
          ) : null}

        </>
      ) : (
        <>
          <section className="card" aria-labelledby="progress-heading">
            <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
              <h1 id="progress-heading">
                {job.done} of {job.total} checked
              </h1>
              <span style={{ marginLeft: "auto", display: "flex", gap: 12 }}>
                {job.state === "running" ? (
                  <button
                    type="button"
                    className="button"
                    onClick={() => stopBatch(job.job_id).then(setJob)}
                  >
                    Stop
                  </button>
                ) : null}
                <a className="button button--primary" href={exportUrl(job.job_id)} download>
                  Export all results (CSV)
                </a>
              </span>
            </div>
            <div
              className="progress"
              style={{ marginTop: 16, maxWidth: "none" }}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={job.total}
              aria-valuenow={job.done}
              aria-label="Labels checked so far"
            >
              <div
                className="progress__fill"
                style={{ width: `${job.total ? (job.done / job.total) * 100 : 0}%` }}
              />
            </div>
            <p className="help">
              {minutes(job.elapsed_seconds)} so far
              {job.state === "running" && job.estimated_seconds_remaining
                ? ` · about ${minutes(job.estimated_seconds_remaining)} left, at the speed measured so far`
                : ""}
              {job.state === "finished" ? " · finished" : ""}
              {job.state === "stopped" ? " · stopped; everything already checked is kept" : ""}
            </p>
          </section>

          <section className="card" aria-labelledby="table-heading">
            <h2 id="table-heading">Results, problems first</h2>
            <div className="filter-row">
              {FILTERS.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className="button"
                  aria-pressed={filter === option.key}
                  onClick={() => setFilter(option.key)}
                >
                  {option.label} ({countFor(option.key)})
                </button>
              ))}
            </div>

            <table className="batch-table">
              <caption className="visually-hidden">
                Every label checked so far, worst outcome first
              </caption>
              <thead>
                <tr>
                  <th scope="col">Status</th>
                  <th scope="col">Application ID</th>
                  <th scope="col">Brand name</th>
                  <th scope="col">Issues</th>
                  <th scope="col">Image</th>
                </tr>
              </thead>
              <tbody>
                {results.map((rowResult) => (
                  <tr key={`${rowResult.application_id}-${rowResult.image}`}>
                    <td>
                      {rowResult.outcome === "error" ? (
                        <span className="badge badge--unreadable">
                          <span className="badge__glyph" aria-hidden="true">
                            !
                          </span>
                          Could not be checked
                        </span>
                      ) : (
                        <VerdictBadge verdict={rowResult.outcome as Outcome} small />
                      )}
                    </td>
                    <td className="mono">
                      {rowResult.application_id}
                    </td>
                    <td>{rowResult.brand_name ?? "not read"}</td>
                    <td>
                      {rowResult.issues ? `${rowResult.issues} issues` : "none"}
                    </td>
                    <td className="filename">
                      {rowResult.image}
                      {rowResult.error ? `. ${rowResult.error.message}` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {results.length === 0 ? (
              <p className="help">Nothing in this filter yet.</p>
            ) : null}
          </section>
        </>
      )}
    </div>
  );
}
