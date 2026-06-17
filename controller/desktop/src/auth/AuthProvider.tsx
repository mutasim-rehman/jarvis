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
  type PreferenceSettings,
} from "../lib/backendApi";
import {
  ensureBackendRunning,
  formatBackendError,
  resolveBackendBaseUrl,
} from "../lib/backendReady";
import { getSupabase } from "./supabaseClient";

type AuthContextValue = {
  loading: boolean;
  backendConnecting: boolean;
  session: Session | null;
  accessToken: string | null;
  me: AuthMeResponse | null;
  backendAuthError: string | null;
  onboardingCompleted: boolean;
  refreshMe: (baseUrl?: string) => Promise<void>;
  markOnboardingComplete: (settings?: Partial<PreferenceSettings>) => void;
  resolveAccessToken: () => Promise<string | null>;
  signOut: () => Promise<void>;
  supabaseEnabled: boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(isSupabaseConfigured());
  const [backendConnecting, setBackendConnecting] = useState(false);
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

  const markOnboardingComplete = useCallback((settings?: Partial<PreferenceSettings>) => {
    setMe((prev) => {
      const baseSettings: PreferenceSettings = prev?.settings ?? {
        version: 1,
        onboarding_completed: false,
        sliders: {
          honesty: 0.7,
          humor: 0.4,
          formality: 0.6,
          verbosity: 0.5,
          proactivity: 0.5,
        },
      };
      const nextSettings: PreferenceSettings = {
        ...baseSettings,
        ...settings,
        onboarding_completed: true,
      };
      return {
        user_id: prev?.user_id ?? session?.user.id ?? "",
        email: prev?.email ?? session?.user.email ?? null,
        settings: nextSettings,
        onboarding_completed: true,
      };
    });
    setBackendAuthError(null);
  }, [session?.user.email, session?.user.id]);

  const refreshMe = useCallback(async (baseUrl?: string) => {
    const token = await resolveAccessToken();
    if (!token) {
      setMe(null);
      setBackendAuthError(null);
      setBackendConnecting(false);
      return;
    }
    let resolvedBase = baseUrl ?? (await resolveBackendBaseUrl());
    setBackendConnecting(true);
    try {
      resolvedBase = await ensureBackendRunning();
      const data = await fetchAuthMe(resolvedBase, token);
      setMe(data);
      setBackendAuthError(null);
      try {
        await registerDevice(resolvedBase, token);
      } catch {
        // non-fatal
      }
    } catch (err) {
      setMe(null);
      setBackendAuthError(formatBackendError(err, resolvedBase));
    } finally {
      setBackendConnecting(false);
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
      backendConnecting,
      session,
      accessToken: session?.access_token ?? null,
      me,
      backendAuthError,
      onboardingCompleted: me?.onboarding_completed ?? false,
      refreshMe,
      markOnboardingComplete,
      resolveAccessToken,
      signOut: signOutUser,
      supabaseEnabled: isSupabaseConfigured(),
    }),
    [
      loading,
      backendConnecting,
      session,
      me,
      backendAuthError,
      refreshMe,
      markOnboardingComplete,
      resolveAccessToken,
      signOutUser,
    ],
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
