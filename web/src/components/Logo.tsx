/**
 * The TTB seal.
 *
 * Served as a file rather than inlined: the asset ships with its own <style>
 * block using single-letter class names, which would collide with the app's
 * stylesheet the moment it were pasted into the document.
 *
 * The intrinsic dimensions are declared even though CSS sets the height. They
 * are what lets the browser reserve the right box before a 44 KB file has
 * loaded, so the wordmark beside it does not jump on first paint.
 *
 * This is a prototype built against a TTB brief, not a TTB product. The alt
 * text describes what the image is rather than asserting who operates the
 * site, and the README says the same in words. See README > Scope.
 */

export function Logo({ className }: { className: string }) {
  return (
    <img
      className={className}
      src="/ttb-logo.svg"
      width={262}
      height={64}
      alt="Alcohol and Tobacco Tax and Trade Bureau seal"
    />
  );
}
