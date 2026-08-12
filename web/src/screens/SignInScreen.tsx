import { useState } from "react";

import { ApiError, signIn } from "../api/client";
import { Logo } from "../components/Logo";

/**
 * The gate on a public URL.
 *
 * Not an identity system. One shared credential, no accounts, no reset, and
 * the copy says so rather than implying a password anyone could recover. The
 * credential is delivered out of band; nothing on this page hints at it, which
 * would defeat the point of having it.
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
    <section className="card card--narrow">
      <Logo className="signin__logo" />
      <h1>Sign in</h1>
      <p className="help">
        Alcohol Label Verification compares label artwork against the values
        declared in a COLA application.
      </p>

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

        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {busy ? null : (
          <p className="help" style={{ marginTop: 12 }}>
            One shared account for the review team. If you do not have the
            details, ask whoever sent you this link.
          </p>
        )}
      </form>
    </section>
  );
}
