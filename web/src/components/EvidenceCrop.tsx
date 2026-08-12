import { useState } from "react";

import { Lightbox } from "./Lightbox";

/**
 * The region of the image a verdict came from.
 *
 * This is the heart of the results screen. It is what lets an agent tell "the
 * label is genuinely wrong" from "we misread it" in about a second, and it is
 * the whole answer to a 28-year veteran's scepticism. It is never behind a
 * click, a hover, or a disclosure (docs/ui-spec.md, Screen 3); the click adds
 * a larger view, it does not gate the small one.
 *
 * A field that is not on the label has no region to show. The panel keeps its
 * dimensions and says so, rather than collapsing and making the row jump
 * (ui-spec resolution 3).
 */

export function EvidenceCrop({
  src,
  fieldName,
  detected,
  tall = false,
}: {
  src: string | null;
  fieldName: string;
  /** Whether the value was read off the label at all. Decides what an empty
   * panel claims: "not found anywhere" is only true when nothing was read;
   * when a value was read but its region could not be located, saying it is
   * absent would be false. */
  detected: boolean;
  tall?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const alt = `The part of the label showing ${fieldName}`;
  const className = `crop${tall ? " crop--tall" : ""}`;
  return (
    <div>
      <p className="micro-label">Evidence from the image</p>
      {src ? (
        <>
          <button
            type="button"
            className={`${className} crop--clickable`}
            onClick={() => setOpen(true)}
          >
            <img src={src} alt={alt} />
            <span className="visually-hidden">Click to enlarge</span>
          </button>
          {open ? <Lightbox src={src} alt={alt} onClose={() => setOpen(false)} /> : null}
        </>
      ) : (
        <div className={className}>
          <p className="crop__empty">
            {detected
              ? "Could not locate this text in the image"
              : "Not found anywhere on the label"}
          </p>
        </div>
      )}
    </div>
  );
}
