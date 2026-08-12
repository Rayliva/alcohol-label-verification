import { useEffect, useMemo, useRef, useState } from "react";

import type { BeverageTypeOption, DeclaredFields } from "../api/types";

/**
 * Screen 1: collect an image and the values declared in the application.
 *
 * One job, one screen, one primary action. The button is disabled until it can
 * work, and a line above it names every missing item by its exact field label.
 * a disabled control that does not explain itself is a dead end
 * (.claude/rules/accessibility.md, rule 9).
 */

interface FieldSpec {
  name: keyof DeclaredFields;
  label: string;
  help: string;
  required: boolean;
  mono?: boolean;
  textarea?: boolean;
  note?: string;
}

const FIELDS: FieldSpec[] = [
  {
    name: "brand_name",
    label: "Brand name",
    help: "The name the product is sold under, e.g. Stone's Throw.",
    required: true,
  },
  {
    name: "class_type",
    label: "Class or type designation",
    help: "What the product legally is, e.g. Straight Bourbon Whiskey.",
    required: true,
  },
  {
    name: "alcohol_content",
    label: "Alcohol content",
    help: "Type it as written on the application, e.g. 45% Alc./Vol. (90 Proof).",
    required: true,
    mono: true,
  },
  {
    name: "net_contents",
    label: "Net contents",
    help: "Volume in metric, e.g. 750 mL.",
    required: true,
    mono: true,
  },
  {
    name: "bottler_address",
    label: "Bottler or producer name and address",
    help: "Full name and address, including street, city and state.",
    required: true,
    textarea: true,
  },
  {
    name: "country_of_origin",
    label: "Country of origin",
    help: "Required only when the product is imported.",
    required: false,
    note: "imports only",
  },
];

export function InputScreen({
  beverageTypes,
  beverageType,
  onBeverageType,
  declared,
  onDeclared,
  image,
  onImage,
  onSubmit,
  onBatch,
  onCancel,
}: {
  beverageTypes: BeverageTypeOption[];
  beverageType: string;
  onBeverageType: (value: string) => void;
  declared: DeclaredFields;
  onDeclared: (next: DeclaredFields) => void;
  image: File | null;
  onImage: (file: File | null) => void;
  onSubmit: () => void;
  onBatch?: () => void;
  /** Back to the queue. Absent on the first screen an agent ever sees. */
  onCancel?: () => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!image) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  const selected = beverageTypes.find((type) => type.beverage_type === beverageType);
  const alcoholRequired = selected?.alcohol_content_required ?? true;

  const missing = useMemo(() => {
    const gaps: string[] = [];
    if (!image) gaps.push("a label image");
    for (const field of FIELDS) {
      const needed = field.name === "alcohol_content" ? alcoholRequired : field.required;
      if (needed && !declared[field.name].trim()) gaps.push(field.label);
    }
    return gaps;
  }, [image, declared, alcoholRequired]);

  const update = (name: keyof DeclaredFields, value: string) =>
    onDeclared({ ...declared, [name]: value });

  return (
    <div className="two-column">
      <div className="stack">
        {onCancel ? (
          <button className="button button--quiet" type="button" onClick={onCancel}>
            ← Back to the queue
          </button>
        ) : null}
        <section className="card" aria-labelledby="artwork-heading">
          <h2 id="artwork-heading">1. The label artwork</h2>
          <p className="help">A photograph or an export of the label. JPG or PNG.</p>

          {image ? (
            <div className="chosen-file" style={{ marginTop: 18 }}>
              {preview ? (
                <img className="chosen-file__preview" src={preview} alt="The label you chose" />
              ) : (
                <div className="chosen-file__preview" />
              )}
              <div>
                <p style={{ margin: 0, fontWeight: 600 }}>{image.name}</p>
                <p className="filename">{Math.round(image.size / 1024)} KB</p>
                <button
                  type="button"
                  className="button"
                  style={{ marginTop: 12 }}
                  onClick={() => {
                    onImage(null);
                    if (fileInput.current) fileInput.current.value = "";
                  }}
                >
                  Remove this file
                </button>
              </div>
            </div>
          ) : (
            <div
              className="dropzone"
              style={{ marginTop: 18 }}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                const dropped = event.dataTransfer.files?.[0];
                if (dropped) onImage(dropped);
              }}
            >
              <p className="dropzone__headline">Drag a label image here</p>
              <p className="help" style={{ marginBottom: 16 }}>
                or use the button below
              </p>
              <button
                type="button"
                className="button"
                onClick={() => fileInput.current?.click()}
              >
                Choose file
              </button>
            </div>
          )}

          <label className="visually-hidden" htmlFor="label-image">
            Label image file
          </label>
          <input
            ref={fileInput}
            id="label-image"
            className="visually-hidden"
            type="file"
            accept="image/png,image/jpeg"
            onChange={(event) => onImage(event.target.files?.[0] ?? null)}
          />
        </section>

        <section className="card" aria-labelledby="type-heading">
          <h2 id="type-heading">2. What kind of drink is it?</h2>
          <p className="help">This decides which rules apply.</p>
          <div className="choice-grid" style={{ marginTop: 16 }}>
            {beverageTypes.map((type) => (
              <button
                key={type.beverage_type}
                type="button"
                className="choice"
                aria-pressed={type.beverage_type === beverageType}
                disabled={!type.available}
                onClick={() => onBeverageType(type.beverage_type)}
              >
                <span aria-hidden="true">
                  {type.beverage_type === beverageType ? "◉" : "○"}{" "}
                </span>
                {type.display_name}
              </button>
            ))}
          </div>
          {beverageTypes
            .filter((type) => !type.available)
            .map((type) => (
              <p className="help" key={type.beverage_type}>
                {type.unavailable_reason}
              </p>
            ))}
        </section>
      </div>

      <section className="card" aria-labelledby="declared-heading">
        <h2 id="declared-heading">3. What the application says</h2>
        <p className="help">
          Copy these from the COLA application, exactly as written. Fields marked{" "}
          <span className="field__required">*</span> are required.
        </p>

        <div style={{ marginTop: 20 }}>
          <div className="field">
            <label className="field__label" htmlFor="application_id">
              Application ID <span className="field__note">(optional)</span>
            </label>
            <input
              id="application_id"
              className="input input--mono"
              value={declared.application_id}
              onChange={(event) => update("application_id", event.target.value)}
            />
            <p className="help">
              The COLA application number, if you have it. Used to label your results.
            </p>
          </div>

          {FIELDS.map((field) => {
            const needed = field.name === "alcohol_content" ? alcoholRequired : field.required;
            // A required field is marked with an asterisk and nothing else. The
            // note is kept for the cases where "optional" alone would not say
            // enough: imports only, or optional for this drink specifically.
            const note = field.name === "alcohol_content" && !alcoholRequired
              ? selected?.alcohol_content_note ?? "optional for this drink"
              : needed
                ? null
                : field.note ?? "optional";
            return (
              <div className="field" key={field.name}>
                <label className="field__label" htmlFor={field.name}>
                  {field.label}{" "}
                  {needed ? (
                    <>
                      <span className="field__required" aria-hidden="true">
                        *
                      </span>
                      <span className="visually-hidden">(required)</span>
                    </>
                  ) : null}
                  {note ? <span className="field__note">({note})</span> : null}
                </label>
                {field.textarea ? (
                  <textarea
                    id={field.name}
                    className="textarea"
                    rows={3}
                    value={declared[field.name]}
                    onChange={(event) => update(field.name, event.target.value)}
                  />
                ) : (
                  <input
                    id={field.name}
                    className={`input${field.mono ? " input--mono" : ""}`}
                    value={declared[field.name]}
                    onChange={(event) => update(field.name, event.target.value)}
                  />
                )}
                <p className="help">{field.help}</p>
              </div>
            );
          })}

          <div className="field">
            <label className="field__label" htmlFor="reviewer">
              Your name or initials <span className="field__note">(optional)</span>
            </label>
            <input
              id="reviewer"
              className="input"
              value={declared.reviewer}
              onChange={(event) => update("reviewer", event.target.value)}
            />
            <p className="help">
              Put on any field you accept or reject, so the record shows who decided.
            </p>
          </div>
        </div>

        <hr className="result__divider" />

        {missing.length ? (
          <p className="blocked">
            Still needed before this button works: {missing.join(", ")}.
          </p>
        ) : (
          <p className="ready">Everything required is filled in.</p>
        )}

        <button
          type="button"
          className="button button--primary button--wide"
          disabled={missing.length > 0}
          onClick={onSubmit}
        >
          Check this label
        </button>

        {onBatch ? (
          <p style={{ marginBottom: 0 }}>
            <button type="button" className="button button--quiet" onClick={onBatch}>
              Have a lot of these? Check a batch of labels instead.
            </button>
          </p>
        ) : null}
      </section>
    </div>
  );
}
