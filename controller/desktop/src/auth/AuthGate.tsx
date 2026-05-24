import { type ReactNode } from "react";
import { useAuth } from "./AuthProvider";
import { OnboardingWizard } from "../onboarding/OnboardingWizard";
import { SignInScreen } from "./SignInScreen";

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
        <div className="auth-card">
          <p className="auth-subtitle">Loading account…</p>
        </div>
      </main>
    );
  }

  if (!session) {
    return <SignInScreen />;
  }

  if (!onboardingCompleted) {
    return <OnboardingWizard />;
  }

  return <>{children}</>;
}
