import { useEffect, useRef, useState } from "react";

/**
 * An image, enlarged on request.
 *
 * Evidence crops and label artwork are shown inline at reading size, which is
 * right for a glance and wrong for small print. Clicking one opens it near
 * viewport size with a zoom toggle for closer still. Esc, the close button,
 * or a click on the dark backdrop dismisses it.
 *
 * Focus is trapped while it is open: aria-modal tells a screen reader the
 * background is inert, so Tab has to agree. Without the trap, two presses of
 * Tab put the user on a control hidden behind the backdrop, with the focus
 * ring invisible (rule 6) and Enter operating a card they cannot see. Focus
 * goes to the close button on open and back to the trigger on close.
 */

export function Lightbox({
  src,
  alt,
  onClose,
}: {
  src: string;
  alt: string;
  onClose: () => void;
}) {
  const [zoomed, setZoomed] = useState(false);
  const dialog = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  // The parent passes an inline closure, so the effect must not key on it:
  // re-running the effect on every parent render bounced focus between the
  // opener and the close button. Kept fresh in a ref instead.
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    closeButton.current?.focus();

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        close.current();
        return;
      }
      if (event.key !== "Tab" || !dialog.current) return;
      const focusable = dialog.current.querySelectorAll<HTMLElement>("button");
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, []);

  // The stage fills the overlay, so "clicked the backdrop" means "clicked
  // inside the overlay or the stage but not on the image or a button".
  const onBackdrop = (event: React.MouseEvent) => {
    if (event.target instanceof HTMLElement && !event.target.closest("img, button")) {
      onClose();
    }
  };

  return (
    <div
      ref={dialog}
      className="lightbox"
      role="dialog"
      aria-modal="true"
      aria-label={`Enlarged: ${alt}`}
      onClick={onBackdrop}
    >
      <div className="lightbox__bar">
        <button
          type="button"
          className="button button--small"
          onClick={() => setZoomed((state) => !state)}
        >
          {zoomed ? "Zoom out" : "Zoom in"}
        </button>
        <button
          ref={closeButton}
          type="button"
          className="button button--small"
          onClick={onClose}
        >
          Close
        </button>
      </div>
      <div className={`lightbox__stage${zoomed ? " lightbox__stage--zoomed" : ""}`}>
        <img src={src} alt={alt} />
      </div>
    </div>
  );
}
