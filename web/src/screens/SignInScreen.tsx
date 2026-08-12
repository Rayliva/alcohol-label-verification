import { useState } from "react";

import { ApiError, signIn } from "../api/client";
import { Logo } from "../components/Logo";

/**
 * The gate on a public URL.
 *
 * Not an identity system. One shared credential, no accounts, no reset. The
 * credential is delivered out of band; nothing on this page hints at it, or
 * even mentions that it is shared — either would help exactly the person the
 * gate exists to keep out. The seal, the product name, and two fields; the
 * screens behind the gate explain the product (decided 2026-08-11).
 */

export function SignInScreen({ onSignedIn }: { onSignedIn: (who: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSignedIn(await signIn(username, password));
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.body.message
          : "Can't reach the service right now. Try again in a moment.",
      );
      setBusy(false);
    }
  };

  return (
    <section className="card card--narrow signin">
      <Logo className="signin__logo" />
      <h1 className="signin__title">Alcohol Label Verification</h1>
      <p className="signin__subtitle">Sign in to review applications</p>

      {error ? (
        <div className="notice notice--error" role="alert">
          <h2>{error}</h2>
          <p style={{ marginBottom: 0 }}>
            Check both the username and the password, then try again.
          </p>
        </div>
      ) : null}

      <form onSubmit={submit}>
        <label className="field">
          <span className="field__label">Username</span>
          <input
            className="input"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>

        <label className="field">
          <span className="field__label">Password</span>
          <input
            className="input"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        <div className="signin__submit">
          <button className="button button--primary" type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </form>
    </section>
  );
}
