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
  onboardingCompleted: boolean;
  refreshMe: (baseUrl: string) => Promise<void>;
  signOut: () => Promise<void>;
  supabaseEnabled: boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const defaultBackend = "http://127.0.0.1:8000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(isSupabaseConfigured());
  const [session, setSession] = useState<Session | null>(null);
  const [me, setMe] = useState<AuthMeResponse | null>(null);

  const refreshMe = useCallback(async (baseUrl: string = defaultBackend) => {
    if (!session?.access_token) {
      setMe(null);
      return;
    }
    const data = await fetchAuthMe(baseUrl, session.access_token);
    setMe(data);
    try {
      await registerDevice(baseUrl, session.access_token);
    } catch {
      // non-fatal
    }
  }, [session?.access_token]);

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
      onboardingCompleted: me?.onboarding_completed ?? false,
      refreshMe,
      signOut: signOutUser,
      supabaseEnabled: isSupabaseConfigured(),
    }),
    [loading, session, me, refreshMe, signOutUser],
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
