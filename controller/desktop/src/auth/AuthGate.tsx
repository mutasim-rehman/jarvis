import { type ReactNode } from "react";
import { signInWithGitHub, signInWithGoogle } from "./supabaseClient";
import { useAuth } from "./AuthProvider";
import { OnboardingWizard } from "../onboarding/OnboardingWizard";

type AuthGateProps = {
  children: ReactNode;
};

export function AuthGate({ children }: AuthGateProps) {
  const { loading, session, supabaseEnabled, onboardingCompleted } = useAuth();

  if (!supabaseEnabled) {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <main className="auth-screen">
        <p>Loading account…</p>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="auth-screen">
        <h1>Sign in to JARVIS</h1>
        <p>Use the same account on desktop, hub, and mobile.</p>
        <div className="auth-actions">
          <button type="button" onClick={() => void signInWithGoogle()}>
            Continue with Google
          </button>
          <button type="button" onClick={() => void signInWithGitHub()}>
            Continue with GitHub
          </button>
        </div>
      </main>
    );
  }

  if (!onboardingCompleted) {
    return <OnboardingWizard />;
  }

  return <>{children}</>;
}
