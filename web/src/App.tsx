import { useEffect, useRef, useState } from "react";

import { ApiError, currentAgent, fetchBeverageTypes, signOut, verifyLabel } from "./api/client";
import type {
  BeverageTypeOption,
  DeclaredFields,
  ErrorBody,
  VerificationResponse,
} from "./api/types";
import { EMPTY_DECLARED } from "./api/types";
import { BatchScreen } from "./screens/BatchScreen";
import { QueueScreen } from "./screens/QueueScreen";
import { ReviewScreen } from "./screens/ReviewScreen";
import { SignInScreen } from "./screens/SignInScreen";
import { InputScreen } from "./screens/InputScreen";
import { ProcessingScreen } from "./screens/ProcessingScreen";
import { ResultsScreen } from "./screens/ResultsScreen";

/**
 * The queue is the front door; one screen at a time from there.
 *
 * There is no router: an agent signs in, lands on the queue, opens one
 * application, and comes back. A URL for each step would be a second concept to
 * explain to an agent who prints their emails.
 */

type Step = "queue" | "review" | "input" | "processing" | "results" | "batch";

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
  const [step, setStep] = useState<Step>("queue");
  const [agent, setAgent] = useState<string | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [openId, setOpenId] = useState<string | null>(null);
  // Bumped whenever the queue's contents change, so it refetches rather than
  // showing a decision that has already been made.
  const [queueVersion, setQueueVersion] = useState(0);
  const [response, setResponse] = useState<VerificationResponse | null>(null);
  const [error, setError] = useState<ErrorBody | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState(0);
  const request = useRef<AbortController | null>(null);

  useEffect(() => {
    currentAgent()
      .then(setAgent)
      .finally(() => setCheckingSession(false));
  }, []);

  useEffect(() => {
    if (!agent) return;
    fetchBeverageTypes()
      .then(setTypes)
      .catch(() => {
        // The selector still works with spirits alone; the API being briefly
        // unreachable must not leave an agent staring at an empty screen.
      });
  }, [agent]);

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
    setUploaded(0);
    setStep("processing");
    const controller = new AbortController();
    request.current = controller;
    try {
      const result = await verifyLabel(
        image,
        beverageType,
        declared,
        controller.signal,
        setUploaded,
      );
      setResponse(result);
      setQueueVersion((version) => version + 1);
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
        {agent && step !== "input" && step !== "batch" && step !== "processing" ? (
          <button
            className="button button--small button--primary"
            type="button"
            onClick={() => setStep("input")}
          >
            <span className="masthead__plus" aria-hidden="true">
              +
            </span>
            Submit new application
          </button>
        ) : null}
        {agent ? (
          <span className="masthead__agent">
            <span className="masthead__who">Signed in as {agent}</span>
            <button
              className="button button--quiet"
              type="button"
              onClick={async () => {
                await signOut();
                setAgent(null);
                setStep("queue");
              }}
            >
              Sign out
            </button>
          </span>
        ) : null}
      </header>

      <main className="page">
        {checkingSession ? null : !agent ? (
          <SignInScreen onSignedIn={setAgent} />
        ) : (
          <>
        {error ? (
          <section className="notice notice--error" style={{ marginBottom: 18 }}>
            <h2>{error.message}</h2>
            <p style={{ marginBottom: 0 }}>{error.what_to_do}</p>
          </section>
        ) : null}

        {step === "queue" ? (
          <QueueScreen
            reloadKey={queueVersion}
            onOpen={(id) => {
              setOpenId(id);
              setStep("review");
            }}
          />
        ) : null}

        {step === "review" && openId ? (
          <ReviewScreen
            id={openId}
            onBack={() => setStep("queue")}
            onDecided={() => {
              setQueueVersion((version) => version + 1);
              setStep("queue");
            }}
          />
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
            onBatch={() => setStep("batch")}
            onCancel={() => setStep("queue")}
          />
        ) : null}

        {step === "batch" ? <BatchScreen onSingle={() => setStep("input")} /> : null}

        {step === "processing" ? (
          <ProcessingScreen
            previewUrl={previewUrl}
            uploaded={uploaded}
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
              setStep("queue");
            }}
          />
        ) : null}
          </>
        )}
      </main>
    </>
  );
}
