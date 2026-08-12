import { useEffect, useState } from "react";

/**
 * Screen 2: make the two-to-five second wait legible.
 *
 * Named stages in plain words, elapsed seconds, and a bar. Never a bare
 * spinner: a previous vendor pilot took 30-40 seconds and agents abandoned it,
 * so silence during the wait is the thing this screen exists to prevent.
 *
 * The stages were once advanced by a timer, on fixed offsets taken from an old
 * measurement. That made "checking each field" the stage on screen whenever the
 * wait ran long, no matter what was actually happening, and it is why a slow
 * check looked like a slow rule engine. Only two things here are known to the
 * browser and both are now measured: how much of the image has gone up, and how
 * long it has been.
 */

const SLOW_AFTER_SECONDS = 10;

/**
 * Median server time over the 31 sample labels, measured against the deployed
 * instance on 2026-08-11. It sets the pace of the bar and nothing else: the bar
 * stops short of full until the answer arrives, so a slow check reads as slow
 * rather than as finished.
 */
const TYPICAL_CHECK_SECONDS = 2.8;

export function ProcessingScreen({
  previewUrl,
  uploaded,
  onCancel,
}: {
  previewUrl: string | null;
  /** Fraction of the image that has reached the server, 0 to 1. */
  uploaded: number;
  onCancel: () => void;
}) {
  const [elapsed, setElapsed] = useState(0);
  const [uploadedAt, setUploadedAt] = useState<number | null>(null);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed((Date.now() - started) / 1000), 100);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (uploaded >= 1) setUploadedAt((at) => at ?? Date.now());
  }, [uploaded]);

  const sending = uploaded < 1;
  const checking = uploadedAt === null ? 0 : (Date.now() - uploadedAt) / 1000;

  // Half the bar is the upload, which is measured. The other half is the check,
  // which is paced by the median and held below full until the answer lands.
  const progress = sending
    ? Math.round(uploaded * 50)
    : Math.min(96, 50 + Math.round((checking / TYPICAL_CHECK_SECONDS) * 46));

  const stages = [
    {
      key: "upload",
      name: sending
        ? `Sending the image, ${Math.round(uploaded * 100)}% of 100% sent`
        : "Sending the image",
      state: sending ? "active" : "done",
    },
    {
      key: "check",
      name: "Reading the label and checking every field",
      state: sending ? "pending" : "active",
    },
  ];

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
          {stages.map((stage) => (
            <li className={`stage stage--${stage.state}`} key={stage.key}>
              <span className="stage__marker" aria-hidden="true">
                {stage.state === "done" ? "✓" : stage.state === "active" ? "…" : "·"}
              </span>
              <span>
                {stage.name}
                {stage.state === "done" ? ", done" : stage.state === "active" ? ", in progress" : ""}
              </span>
            </li>
          ))}
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
        <p className="help" style={{ marginTop: 12 }}>
          {elapsed.toFixed(1)} seconds so far. Most labels come back in about{" "}
          {TYPICAL_CHECK_SECONDS} seconds once the image is up.
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
