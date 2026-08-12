import type { DeclaredFields } from "../api/types";
import { BatchScreen } from "./BatchScreen";
import { InputScreen } from "./InputScreen";

/**
 * One door for new work: check one label, or check a batch.
 *
 * The first question on the page is which one you are doing, and everything
 * below it follows the answer. Single and batch used to be separate screens
 * cross-linked by quiet buttons at the bottom, which meant the way to switch
 * was in the last place anyone looks (product owner, 2026-08-11).
 */

export type SubmitMode = "single" | "batch";

export function SubmitScreen({
  mode,
  onMode,
  onBack,
  declared,
  onDeclared,
  image,
  onImage,
  onSubmit,
}: {
  mode: SubmitMode;
  onMode: (mode: SubmitMode) => void;
  onBack: () => void;
  declared: DeclaredFields;
  onDeclared: (next: DeclaredFields) => void;
  image: File | null;
  onImage: (file: File | null) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="stack form-column">
      <button className="back-link" type="button" onClick={onBack}>
        <span aria-hidden="true">←</span> Back to the queue
      </button>

      <section className="card" aria-labelledby="mode-heading">
        <h2 id="mode-heading">What are you submitting?</h2>
        <div className="mode-toggle">
          <button
            type="button"
            className="button"
            aria-pressed={mode === "single"}
            onClick={() => onMode("single")}
          >
            One label
          </button>
          <button
            type="button"
            className="button"
            aria-pressed={mode === "batch"}
            onClick={() => onMode("batch")}
          >
            A batch of labels
          </button>
        </div>
      </section>

      {/* Hidden, not unmounted. BatchScreen owns its running job, and
          unmounting it mid-batch would strand the job with no progress view,
          no Stop, and no export while the server worked on. display:none
          keeps the polling alive and the job recoverable by toggling back. */}
      <div className="stack" hidden={mode !== "single"}>
        <InputScreen
          declared={declared}
          onDeclared={onDeclared}
          image={image}
          onImage={onImage}
          onSubmit={onSubmit}
        />
      </div>
      <div className="stack" hidden={mode !== "batch"}>
        <BatchScreen />
      </div>
    </div>
  );
}
