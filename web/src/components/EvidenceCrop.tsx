/**
 * The region of the image a verdict came from.
 *
 * This is the heart of the results screen. It is what lets an agent tell "the
 * label is genuinely wrong" from "we misread it" in about a second, and it is
 * the whole answer to a 28-year veteran's scepticism. It is never behind a
 * click, a hover, or a disclosure (docs/ui-spec.md, Screen 3).
 *
 * A field that is not on the label has no region to show. The panel keeps its
 * dimensions and says so, rather than collapsing and making the row jump
 * (ui-spec resolution 3).
 */

export function EvidenceCrop({
  src,
  fieldName,
  tall = false,
}: {
  src: string | null;
  fieldName: string;
  tall?: boolean;
}) {
  const className = `crop${tall ? " crop--tall" : ""}`;
  return (
    <div>
      <p className="micro-label">Evidence from the image</p>
      <div className={className}>
        {src ? (
          <img src={src} alt={`The part of the label showing ${fieldName}`} />
        ) : (
          <p className="crop__empty">Not found anywhere on the label</p>
        )}
      </div>
      <p className="filename">{src ? `crop · ${fieldName}.png` : "no crop — field not present"}</p>
    </div>
  );
}
