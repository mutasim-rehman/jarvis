import { useEffect, useState } from "react";
import { completeOAuthFromUrl, getSupabase } from "./supabaseClient";

export function AuthCallback() {
  const [message, setMessage] = useState("Completing sign-in…");

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      setMessage("Supabase is not configured.");
      return;
    }
    void completeOAuthFromUrl(supabase, window.location.href)
      .then(() => {
        window.location.replace("/");
      })
      .catch((err: Error) => {
        setMessage(err.message || "Sign-in failed.");
      });
  }, []);

  return (
    <main className="auth-screen">
      <div className="auth-card">
        <p className="auth-subtitle">{message}</p>
      </div>
    </main>
  );
}
