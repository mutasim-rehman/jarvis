import { useState } from "react";
import { signInWithGitHub, signInWithGoogle } from "./supabaseClient";
import { GitHubIcon, GoogleIcon } from "./OAuthIcons";

type OAuthProvider = "google" | "github";

function friendlyOAuthError(message: string): string {
  if (/closed before completing/i.test(message)) {
    return "The sign-in window was closed before you finished. You can try again when ready.";
  }
  return message;
}

export function SignInScreen() {
  const [busyProvider, setBusyProvider] = useState<OAuthProvider | null>(null);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [lastProvider, setLastProvider] = useState<OAuthProvider | null>(null);

  const handleSignIn = async (provider: OAuthProvider) => {
    setOauthError(null);
    setLastProvider(provider);
    setBusyProvider(provider);
    try {
      if (provider === "google") {
        await signInWithGoogle();
      } else {
        await signInWithGitHub();
      }
    } catch (err) {
      setOauthError(
        friendlyOAuthError(err instanceof Error ? err.message : "Sign-in failed"),
      );
    } finally {
      setBusyProvider(null);
    }
  };

  const retryLast = () => {
    if (lastProvider) {
      void handleSignIn(lastProvider);
    }
  };

  const dismissError = () => {
    setOauthError(null);
  };

  const label = (provider: OAuthProvider, defaultText: string) => {
    if (busyProvider === provider) {
      return "Opening sign-in window…";
    }
    return defaultText;
  };

  return (
    <main className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="auth-logo" aria-hidden="true">
            J
          </span>
          <h1>Sign in to JARVIS</h1>
        </div>
        <p className="auth-subtitle">
          One account for desktop, hub, and mobile. A sign-in window will open for Google or GitHub.
        </p>
        <div className="auth-actions">
          <button
            type="button"
            className="auth-oauth-btn auth-oauth-google"
            disabled={busyProvider !== null}
            onClick={() => void handleSignIn("google")}
          >
            <GoogleIcon />
            <span>{label("google", "Continue with Google")}</span>
          </button>
          <button
            type="button"
            className="auth-oauth-btn auth-oauth-github"
            disabled={busyProvider !== null}
            onClick={() => void handleSignIn("github")}
          >
            <GitHubIcon />
            <span>{label("github", "Continue with GitHub")}</span>
          </button>
        </div>
        {oauthError ? (
          <div className="auth-error-panel" role="alert">
            <p className="auth-error">{oauthError}</p>
            <div className="auth-error-actions">
              {lastProvider ? (
                <button
                  type="button"
                  className="auth-retry-btn"
                  disabled={busyProvider !== null}
                  onClick={() => void retryLast()}
                >
                  Try again
                  {lastProvider === "google" ? " with Google" : " with GitHub"}
                </button>
              ) : null}
              <button
                type="button"
                className="auth-dismiss-btn"
                disabled={busyProvider !== null}
                onClick={dismissError}
              >
                Dismiss
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </main>
  );
}
