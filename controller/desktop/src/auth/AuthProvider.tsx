import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Session } from "@supabase/supabase-js";
import {
  fetchAuthMe,
  isSupabaseConfigured,
  registerDevice,
  type AuthMeResponse,
} from "../lib/backendApi";
import { getSupabase } from "./supabaseClient";

type AuthContextValue = {
  loading: boolean;
  session: Session | null;
  accessToken: string | null;
  me: AuthMeResponse | null;
  backendAuthError: string | null;
  onboardingCompleted: boolean;
  refreshMe: (baseUrl: string) => Promise<void>;
  resolveAccessToken: () => Promise<string | null>;
  signOut: () => Promise<void>;
  supabaseEnabled: boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const defaultBackend = "http://127.0.0.1:8000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(isSupabaseConfigured());
  const [session, setSession] = useState<Session | null>(null);
  const [me, setMe] = useState<AuthMeResponse | null>(null);
  const [backendAuthError, setBackendAuthError] = useState<string | null>(null);

  const resolveAccessToken = useCallback(async (): Promise<string | null> => {
    const supabase = getSupabase();
    if (!supabase) {
      return null;
    }
    const { data, error } = await supabase.auth.getSession();
    if (!error && data.session?.access_token) {
      setSession(data.session);
      return data.session.access_token;
    }
    const refreshed = await supabase.auth.refreshSession();
    if (refreshed.data.session?.access_token) {
      setSession(refreshed.data.session);
      return refreshed.data.session.access_token;
    }
    return null;
  }, []);

  const refreshMe = useCallback(async (baseUrl: string = defaultBackend) => {
    const token = await resolveAccessToken();
    if (!token) {
      setMe(null);
      setBackendAuthError(null);
      return;
    }
    try {
      const data = await fetchAuthMe(baseUrl, token);
      setMe(data);
      setBackendAuthError(null);
      try {
        await registerDevice(baseUrl, token);
      } catch {
        // non-fatal
      }
    } catch (err) {
      setMe(null);
      setBackendAuthError(
        err instanceof Error ? err.message : "Could not verify account with the backend",
      );
    }
  }, [resolveAccessToken]);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      setLoading(false);
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session?.access_token) {
      setMe(null);
      if (typeof window !== "undefined" && window.desktopApi?.setAuthSession) {
        void window.desktopApi.setAuthSession(null, null);
      }
      return;
    }
    void refreshMe().catch(() => setMe(null));
  }, [session?.access_token, refreshMe]);

  useEffect(() => {
    if (!isSupabaseConfigured() || typeof window === "undefined") {
      return;
    }
    const token = session?.access_token ?? null;
    const deviceId = token ? (localStorage.getItem("jarvis_device_id") ?? null) : null;
    if (window.desktopApi?.setAuthSession) {
      void window.desktopApi.setAuthSession(token, deviceId);
    }
  }, [session?.access_token]);

  const signOutUser = useCallback(async () => {
    const supabase = getSupabase();
    if (supabase) {
      await supabase.auth.signOut();
    }
    setMe(null);
    setSession(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      loading,
      session,
      accessToken: session?.access_token ?? null,
      me,
      backendAuthError,
      onboardingCompleted: me?.onboarding_completed ?? false,
      refreshMe,
      resolveAccessToken,
      signOut: signOutUser,
      supabaseEnabled: isSupabaseConfigured(),
    }),
    [loading, session, me, backendAuthError, refreshMe, resolveAccessToken, signOutUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
