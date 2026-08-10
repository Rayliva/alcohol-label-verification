import { useEffect, useState } from "react";

/**
 * Screen 2 — make the two-to-five second wait legible.
 *
 * Named stages in plain words, elapsed seconds, and a determinate bar. Never a
 * bare spinner: a previous vendor pilot took 30-40 seconds and agents abandoned
 * it, so silence during the wait is the thing this screen exists to prevent.
 */

const STAGES = [
  "Uploading the image",
  "Reading the text on the label",
  "Checking each field against the application",
];

/** Roughly where each stage begins, from the measured per-stage timings. */
const STAGE_AT_SECONDS = [0, 0.6, 1.8];
const SLOW_AFTER_SECONDS = 10;

export function ProcessingScreen({
  previewUrl,
  onCancel,
}: {
  previewUrl: string | null;
  onCancel: () => void;
}) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed((Date.now() - started) / 1000), 100);
    return () => window.clearInterval(timer);
  }, []);

  const current = STAGE_AT_SECONDS.filter((at) => elapsed >= at).length - 1;
  const progress = Math.min(95, Math.round((elapsed / 3) * 100));

  return (
    <section className="card processing" aria-labelledby="processing-heading">
      {previewUrl ? (
        <img className="chosen-file__preview" src={previewUrl} alt="The label being checked" />
      ) : (
        <div className="chosen-file__preview" />
      )}
      <div>
        <h1 id="processing-heading">Checking this label</h1>
        <ol className="stages" style={{ marginTop: 20 }}>
          {STAGES.map((stage, index) => {
            const state = index < current ? "done" : index === current ? "active" : "pending";
            return (
              <li className={`stage stage--${state}`} key={stage}>
                <span className="stage__marker" aria-hidden="true">
                  {state === "done" ? "✓" : state === "active" ? "…" : "·"}
                </span>
                <span>
                  {stage}
                  {state === "done" ? " — done" : state === "active" ? " — in progress" : ""}
                </span>
              </li>
            );
          })}
        </ol>

        <div
          className="progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
          aria-label="How far through the check we are"
        >
          <div className="progress__fill" style={{ width: `${progress}%` }} />
        </div>
        <p className="mono" style={{ marginTop: 12 }}>
          {elapsed.toFixed(1)} seconds so far.
        </p>

        {elapsed > SLOW_AFTER_SECONDS ? (
          <div className="notice notice--warn" style={{ marginTop: 16 }}>
            <p style={{ margin: 0, fontWeight: 700 }}>This is taking longer than usual</p>
            <p style={{ margin: "6px 0 12px" }}>
              The reading service is slow right now. Your entry is saved either way.
            </p>
            <button type="button" className="button" onClick={onCancel}>
              Cancel and go back
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
