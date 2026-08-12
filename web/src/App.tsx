import { useEffect, useRef, useState } from "react";

import { ApiError, currentAgent, signOut, verifyLabel } from "./api/client";
import type { DeclaredFields, ErrorBody, VerificationResponse } from "./api/types";
import { EMPTY_DECLARED } from "./api/types";
import { Logo } from "./components/Logo";
import { QueueScreen } from "./screens/QueueScreen";
import { ReviewScreen } from "./screens/ReviewScreen";
import { SignInScreen } from "./screens/SignInScreen";
import { SubmitScreen } from "./screens/SubmitScreen";
import type { SubmitMode } from "./screens/SubmitScreen";
import { ProcessingScreen } from "./screens/ProcessingScreen";
import { ResultsScreen } from "./screens/ResultsScreen";

/**
 * The queue is the front door; one screen at a time from there.
 *
 * There is no router: an agent signs in, lands on the queue, opens one
 * application, and comes back. A URL for each step would be a second concept to
 * explain to an agent who prints their emails.
 */

type Step = "queue" | "review" | "submit" | "processing" | "results";

export default function App() {
  const [declared, setDeclared] = useState<DeclaredFields>(EMPTY_DECLARED);
  const [mode, setMode] = useState<SubmitMode>("single");
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
      // Spirits is the product's scope; there is no selector (ui-spec, 2026-08-11).
      const result = await verifyLabel(image, "spirits", declared, controller.signal, setUploaded);
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
      setStep("submit");
    }
  };

  return (
    <>
      {agent ? (
      <header className="masthead">
        <button
          className="masthead__home"
          type="button"
          onClick={() => {
            // Going home mid-check is a cancel: without the abort, the
            // in-flight request resolves seconds later and yanks the user
            // off the queue onto the results screen.
            if (step === "processing") request.current?.abort();
            setStep("queue");
          }}
        >
          <Logo className="masthead__logo" />
          <span className="masthead__name">Alcohol Label Verification</span>
          <span className="visually-hidden">, back to the queue</span>
        </button>
        {step !== "submit" && step !== "processing" ? (
          <button
            className="button button--small button--primary"
            type="button"
            onClick={() => setStep("submit")}
          >
            <span className="masthead__plus" aria-hidden="true">
              +
            </span>
            Submit new application
          </button>
        ) : null}
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
      </header>
      ) : null}

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

        {step === "submit" ? (
          <SubmitScreen
            mode={mode}
            onMode={setMode}
            onBack={() => setStep("queue")}
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
            uploaded={uploaded}
            onCancel={() => {
              request.current?.abort();
              setStep("submit");
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
