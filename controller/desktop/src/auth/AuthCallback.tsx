import { useEffect, useState } from "react";
import { getSupabase } from "./supabaseClient";

export function AuthCallback() {
  const [message, setMessage] = useState("Completing sign-in…");

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      setMessage("Supabase is not configured.");
      return;
    }
    supabase.auth
      .getSession()
      .then(() => {
        window.location.replace("/");
      })
      .catch((err: Error) => {
        setMessage(err.message || "Sign-in failed.");
      });
  }, []);

  return (
    <main className="auth-screen">
      <p>{message}</p>
    </main>
  );
}
