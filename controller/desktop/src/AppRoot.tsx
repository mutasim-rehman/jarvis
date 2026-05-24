import App from "./App";
import { AuthCallback } from "./auth/AuthCallback";
import { AuthGate } from "./auth/AuthGate";
import { AuthProvider } from "./auth/AuthProvider";

export default function AppRoot() {
  if (window.location.pathname === "/auth/callback") {
    return <AuthCallback />;
  }

  return (
    <AuthProvider>
      <AuthGate>
        <App />
      </AuthGate>
    </AuthProvider>
  );
}
