import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";

/** Loopback redirect for Electron OAuth (system browser → desktop app). */
export const ELECTRON_OAUTH_REDIRECT = "http://127.0.0.1:52847/auth/callback";

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  const url = import.meta.env.VITE_SUPABASE_URL?.trim();
  const key = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();
  if (!url || !key) {
    return null;
  }
  if (!client) {
    client = createClient(url, key, {
      auth: {
        flowType: "pkce",
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: false,
      },
    });
  }
  return client;
}

function hasElectronOAuthBridge(): boolean {
  return (
    typeof window !== "undefined" &&
    Boolean(window.desktopApi?.openOAuthWindow || window.desktopApi?.openExternalUrl)
  );
}

export async function completeOAuthFromUrl(
  supabase: SupabaseClient,
  callbackUrl: string,
): Promise<void> {
  const url = new URL(callbackUrl);
  const oauthError = url.searchParams.get("error_description") || url.searchParams.get("error");
  if (oauthError) {
    throw new Error(oauthError);
  }

  const code = url.searchParams.get("code");
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (error) {
      throw error;
    }
    return;
  }

  const hash = url.hash.startsWith("#") ? url.hash.slice(1) : url.hash;
  const params = new URLSearchParams(hash);
  const access_token = params.get("access_token");
  const refresh_token = params.get("refresh_token");
  if (access_token && refresh_token) {
    const { error } = await supabase.auth.setSession({ access_token, refresh_token });
    if (error) {
      throw error;
    }
    return;
  }

  throw new Error(
    "Sign-in did not complete. Add http://127.0.0.1:52847/auth/callback to Supabase redirect URLs and try again.",
  );
}

async function signInWithProviderExternal(provider: "google" | "github"): Promise<void> {
  const supabase = getSupabase();
  if (!supabase) {
    throw new Error("Supabase is not configured");
  }

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo: ELECTRON_OAUTH_REDIRECT,
      skipBrowserRedirect: true,
    },
  });
  if (error) {
    throw error;
  }
  if (!data?.url) {
    throw new Error("No OAuth URL returned from Supabase");
  }

  // Electron window captures ?code= and #access_token= (system browser cannot send hash to localhost).
  if (window.desktopApi?.openOAuthWindow) {
    const result = await window.desktopApi.openOAuthWindow(data.url);
    if (!result.ok || !result.callbackUrl) {
      throw new Error(result.error || "Sign-in window closed before completing");
    }
    await completeOAuthFromUrl(supabase, result.callbackUrl);
    return;
  }

  // Fallback: system browser + loopback (PKCE query ?code= only).
  const listenerReady = new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      reject(new Error("Sign-in timed out. Close the browser tab and try again."));
    }, 5 * 60 * 1000);

    const unsubscribe = window.desktopApi.onOAuthCallback(async (callbackUrl) => {
      window.clearTimeout(timeout);
      unsubscribe();
      try {
        await completeOAuthFromUrl(supabase, callbackUrl);
        resolve();
      } catch (err) {
        reject(err);
      }
    });
  });

  const started = await window.desktopApi.startOAuthListener();
  if (!started.ok) {
    throw new Error(started.error || "Could not start OAuth callback listener");
  }

  const opened = await window.desktopApi.openExternalUrl(data.url);
  if (!opened.ok) {
    throw new Error(opened.error || "Could not open system browser");
  }

  await listenerReady;
}

async function signInWithProviderInApp(provider: "google" | "github"): Promise<void> {
  const supabase = getSupabase();
  if (!supabase) {
    throw new Error("Supabase is not configured");
  }
  const redirectTo = `${window.location.origin}/auth/callback`;
  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo },
  });
  if (error) {
    throw error;
  }
}

export async function signInWithGoogle(): Promise<void> {
  if (hasElectronOAuthBridge()) {
    await signInWithProviderExternal("google");
    return;
  }
  await signInWithProviderInApp("google");
}

export async function signInWithGitHub(): Promise<void> {
  if (hasElectronOAuthBridge()) {
    await signInWithProviderExternal("github");
    return;
  }
  await signInWithProviderInApp("github");
}

export async function signOut(): Promise<void> {
  const supabase = getSupabase();
  if (supabase) {
    await supabase.auth.signOut();
  }
}

export async function getSession(): Promise<Session | null> {
  const supabase = getSupabase();
  if (!supabase) {
    return null;
  }
  const { data } = await supabase.auth.getSession();
  return data.session;
}
