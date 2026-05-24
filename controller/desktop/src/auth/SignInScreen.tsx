import { useState } from "react";
import { signInWithGitHub, signInWithGoogle } from "./supabaseClient";
import { GitHubIcon, GoogleIcon } from "./OAuthIcons";

type OAuthProvider = "google" | "github";

export function SignInScreen() {
  const [busyProvider, setBusyProvider] = useState<OAuthProvider | null>(null);
  const [oauthError, setOauthError] = useState<string | null>(null);

  const handleSignIn = async (provider: OAuthProvider) => {
    setOauthError(null);
    setBusyProvider(provider);
    try {
      if (provider === "google") {
        await signInWithGoogle();
      } else {
        await signInWithGitHub();
      }
    } catch (err) {
      setOauthError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setBusyProvider(null);
    }
  };

  const label = (provider: OAuthProvider, defaultText: string) => {
    if (busyProvider === provider) {
      return "Opening in browser…";
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
          One account for desktop, hub, and mobile. You&apos;ll sign in in your browser, then return
          here.
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
        {oauthError ? <p className="auth-error">{oauthError}</p> : null}
      </div>
    </main>
  );
}
