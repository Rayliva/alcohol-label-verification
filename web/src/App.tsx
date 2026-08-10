import { useEffect, useRef, useState } from "react";

import { ApiError, fetchBeverageTypes, verifyLabel } from "./api/client";
import type {
  BeverageTypeOption,
  DeclaredFields,
  ErrorBody,
  VerificationResponse,
} from "./api/types";
import { EMPTY_DECLARED } from "./api/types";
import { InputScreen } from "./screens/InputScreen";
import { ProcessingScreen } from "./screens/ProcessingScreen";
import { ResultsScreen } from "./screens/ResultsScreen";

/**
 * One label, checked, on one screen at a time.
 *
 * There is no router: the flow is input → processing → results and back, and a
 * URL for each step would be a second concept to explain to an agent who prints
 * their emails.
 */

type Step = "input" | "processing" | "results";

const FALLBACK_TYPES: BeverageTypeOption[] = [
  {
    beverage_type: "spirits",
    display_name: "Spirits",
    citation: "27 CFR part 5",
    available: true,
    unavailable_reason: null,
    alcohol_content_required: true,
    alcohol_content_note: null,
  },
];

export default function App() {
  const [types, setTypes] = useState<BeverageTypeOption[]>(FALLBACK_TYPES);
  const [beverageType, setBeverageType] = useState("spirits");
  const [declared, setDeclared] = useState<DeclaredFields>(EMPTY_DECLARED);
  const [image, setImage] = useState<File | null>(null);
  const [step, setStep] = useState<Step>("input");
  const [response, setResponse] = useState<VerificationResponse | null>(null);
  const [error, setError] = useState<ErrorBody | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchBeverageTypes()
      .then(setTypes)
      .catch(() => {
        // The selector still works with spirits alone; the API being briefly
        // unreachable must not leave an agent staring at an empty screen.
      });
  }, []);

  useEffect(() => {
    if (!image) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  const submit = async () => {
    if (!image) return;
    setError(null);
    setStep("processing");
    const controller = new AbortController();
    request.current = controller;
    try {
      const result = await verifyLabel(image, beverageType, declared, controller.signal);
      setResponse(result);
      setStep("results");
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setError(
        cause instanceof ApiError
          ? cause.body
          : {
              code: "unexpected_error",
              message: "Something went wrong while checking this label.",
              what_to_do: "Try again. Your entry has been kept.",
            },
      );
      setStep("input");
    }
  };

  return (
    <>
      <header className="masthead">
        <span className="masthead__name">Label Check</span>
        <span className="masthead__what">
          Compares label artwork against the values declared in a COLA application
        </span>
      </header>

      <main className="page">
        {error ? (
          <section className="notice notice--error" style={{ marginBottom: 18 }}>
            <h2>{error.message}</h2>
            <p style={{ marginBottom: 0 }}>{error.what_to_do}</p>
          </section>
        ) : null}

        {step === "input" ? (
          <InputScreen
            beverageTypes={types}
            beverageType={beverageType}
            onBeverageType={setBeverageType}
            declared={declared}
            onDeclared={setDeclared}
            image={image}
            onImage={setImage}
            onSubmit={submit}
          />
        ) : null}

        {step === "processing" ? (
          <ProcessingScreen
            previewUrl={previewUrl}
            onCancel={() => {
              request.current?.abort();
              setStep("input");
            }}
          />
        ) : null}

        {step === "results" && response ? (
          <ResultsScreen
            response={response}
            reviewer={declared.reviewer}
            onCheckAnother={() => {
              setResponse(null);
              setImage(null);
              setStep("input");
            }}
          />
        ) : null}
      </main>
    </>
  );
}
