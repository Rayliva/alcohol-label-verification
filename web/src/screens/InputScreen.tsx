import { useEffect, useMemo, useRef, useState } from "react";

import type { DeclaredFields } from "../api/types";

/**
 * Screen 1: collect an image and the values declared in the application.
 *
 * One job, one screen, one primary action. The button is always enabled;
 * pressing it with something missing names every missing item in an alert
 * rather than parking a permanent status line above the button. A disabled
 * control would need adjacent text explaining why
 * (.claude/rules/accessibility.md, rule 9); an enabled one that explains
 * itself on demand needs nothing until asked.
 *
 * There is no beverage type selector. Spirits is the product's scope, and a
 * selector offering two disabled choices was two explanations nobody needed
 * (decided 2026-08-11; see docs/ui-spec.md).
 */

interface FieldSpec {
  name: keyof DeclaredFields;
  label: string;
  help?: string;
  required: boolean;
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
    help: "e.g. 45% Alc./Vol. (90 Proof).",
    required: true,
  },
  {
    name: "net_contents",
    label: "Net contents",
    help: "Volume in metric, e.g. 750 mL.",
    required: true,
  },
  {
    name: "bottler_address",
    label: "Bottler or producer name and address",
    help: "Name, city and state. A street address is optional (27 CFR 5.66).",
    required: true,
    textarea: true,
  },
  {
    name: "country_of_origin",
    label: "Country of origin",
    // No help line: the "(imports only)" note beside the label already says
    // the whole rule.
    required: false,
    note: "imports only",
  },
];

export function InputScreen({
  declared,
  onDeclared,
  image,
  onImage,
  onSubmit,
}: {
  declared: DeclaredFields;
  onDeclared: (next: DeclaredFields) => void;
  image: File | null;
  onImage: (file: File | null) => void;
  onSubmit: () => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [attempted, setAttempted] = useState(false);

  useEffect(() => {
    if (!image) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  const missing = useMemo(() => {
    const gaps: string[] = [];
    if (!image) gaps.push("a label image");
    for (const field of FIELDS) {
      if (field.required && !declared[field.name].trim()) gaps.push(field.label);
    }
    return gaps;
  }, [image, declared]);

  const update = (name: keyof DeclaredFields, value: string) =>
    onDeclared({ ...declared, [name]: value });

  const submit = () => {
    if (missing.length) {
      setAttempted(true);
      return;
    }
    setAttempted(false);
    onSubmit();
  };

  return (
    <>
      <section className="card" aria-labelledby="artwork-heading">
          <h2 id="artwork-heading">The label artwork</h2>
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
                  onClick={() => onImage(null)}
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
            onChange={(event) => {
              // Reset after reading, so choosing the same file again after
              // removing it still fires a change event.
              onImage(event.target.files?.[0] ?? null);
              event.target.value = "";
            }}
          />
      </section>

      <section className="card" aria-labelledby="declared-heading">
        <h2 id="declared-heading">What the application says</h2>
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
              className="input"
              value={declared.application_id}
              onChange={(event) => update("application_id", event.target.value)}
            />
            <p className="help">
              The COLA application number, if you have it. Used to label your results.
            </p>
          </div>

          {FIELDS.map((field) => (
            <div className="field" key={field.name}>
              <label className="field__label" htmlFor={field.name}>
                {field.label}{" "}
                {field.required ? (
                  <>
                    <span className="field__required" aria-hidden="true">
                      *
                    </span>
                    <span className="visually-hidden">(required)</span>
                  </>
                ) : null}
                {field.note ? <span className="field__note">({field.note})</span> : null}
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
                  className="input"
                  value={declared[field.name]}
                  onChange={(event) => update(field.name, event.target.value)}
                />
              )}
              {field.help ? <p className="help">{field.help}</p> : null}
            </div>
          ))}

        </div>

        <hr className="result__divider" />

        {attempted && missing.length ? (
          <p className="blocked" role="alert">
            Still needed before this label can be checked: {missing.join(", ")}.
          </p>
        ) : null}

        <button
          type="button"
          className="button button--primary button--wide"
          onClick={submit}
        >
          Check this label
        </button>

      </section>
    </>
  );
}
