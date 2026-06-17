import { getDeviceType, getOrCreateDeviceId } from "./deviceId";

export type PreferenceSliders = {
  honesty: number;
  humor: number;
  formality: number;
  verbosity: number;
  proactivity: number;
};

export type PreferenceSettings = {
  version: number;
  onboarding_completed: boolean;
  sliders: PreferenceSliders;
};

export type AuthMeResponse = {
  user_id: string;
  email: string | null;
  settings: PreferenceSettings;
  onboarding_completed: boolean;
};

function apiHeaders(accessToken: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Device-Id": getOrCreateDeviceId(),
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  return headers;
}

async function requestBackend<T>(
  baseUrl: string,
  path: string,
  accessToken: string | null,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  const api = typeof window !== "undefined" ? window.desktopApi : undefined;
  if (api?.fetchBackend) {
    const result = await api.fetchBackend({
      method: init.method ?? "GET",
      path,
      baseUrl,
      accessToken,
      deviceId: getOrCreateDeviceId(),
      body: init.body,
    });
    if (!result.ok) {
      const err = new Error(result.error || `${path} failed: ${result.status}`);
      throw err;
    }
    return result.data as T;
  }

  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}${path}`, {
    method: init.method ?? "GET",
    headers: apiHeaders(accessToken),
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${path} failed: ${response.status} ${text}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function fetchAuthMe(
  baseUrl: string,
  accessToken: string,
): Promise<AuthMeResponse> {
  return requestBackend<AuthMeResponse>(baseUrl, "/auth/me", accessToken);
}

export async function patchPreferences(
  baseUrl: string,
  accessToken: string,
  body: Record<string, unknown>,
): Promise<void> {
  await requestBackend<void>(baseUrl, "/preferences", accessToken, {
    method: "PATCH",
    body,
  });
}

export async function importPersonality(
  baseUrl: string,
  accessToken: string,
  document: unknown,
): Promise<void> {
  await requestBackend<void>(baseUrl, "/preferences/personality", accessToken, {
    method: "POST",
    body: document,
  });
}

export async function fetchPersonalityTemplate(
  baseUrl: string,
  accessToken: string,
): Promise<unknown> {
  return requestBackend<unknown>(
    baseUrl,
    "/preferences/personality/template",
    accessToken,
  );
}

export type AccountDeleteResult = {
  deleted: boolean;
  auth_user_removed: boolean;
};

export async function deleteAccount(
  baseUrl: string,
  accessToken: string,
): Promise<AccountDeleteResult> {
  return requestBackend<AccountDeleteResult>(baseUrl, "/auth/account", accessToken, {
    method: "DELETE",
  });
}

export async function registerDevice(
  baseUrl: string,
  accessToken: string,
): Promise<void> {
  await requestBackend<void>(baseUrl, "/devices/register", accessToken, {
    method: "POST",
    body: {
      device_id: getOrCreateDeviceId(),
      device_type: getDeviceType(),
      label: "Desktop",
    },
  });
}

export function isSupabaseConfigured(): boolean {
  const url = import.meta.env.VITE_SUPABASE_URL?.trim();
  const key = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();
  return Boolean(url && key);
}
