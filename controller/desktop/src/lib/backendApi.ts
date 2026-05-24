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

export async function fetchAuthMe(
  baseUrl: string,
  accessToken: string,
): Promise<AuthMeResponse> {
  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/auth/me`, {
    headers: apiHeaders(accessToken),
  });
  if (!response.ok) {
    throw new Error(`auth/me failed: ${response.status}`);
  }
  return response.json() as Promise<AuthMeResponse>;
}

export async function patchPreferences(
  baseUrl: string,
  accessToken: string,
  body: Record<string, unknown>,
): Promise<void> {
  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/preferences`, {
    method: "PATCH",
    headers: apiHeaders(accessToken),
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`preferences patch failed: ${response.status} ${text}`);
  }
}

export async function importPersonality(
  baseUrl: string,
  accessToken: string,
  document: unknown,
): Promise<void> {
  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/preferences/personality`, {
    method: "POST",
    headers: apiHeaders(accessToken),
    body: JSON.stringify(document),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`personality import failed: ${response.status} ${text}`);
  }
}

export async function fetchPersonalityTemplate(
  baseUrl: string,
  accessToken: string,
): Promise<unknown> {
  const response = await fetch(
    `${baseUrl.replace(/\/+$/, "")}/preferences/personality/template`,
    { headers: apiHeaders(accessToken) },
  );
  if (!response.ok) {
    throw new Error(`template fetch failed: ${response.status}`);
  }
  return response.json();
}

export type AccountDeleteResult = {
  deleted: boolean;
  auth_user_removed: boolean;
};

export async function deleteAccount(
  baseUrl: string,
  accessToken: string,
): Promise<AccountDeleteResult> {
  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/auth/account`, {
    method: "DELETE",
    headers: apiHeaders(accessToken),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`account delete failed: ${response.status} ${text}`);
  }
  return response.json() as Promise<AccountDeleteResult>;
}

export async function registerDevice(
  baseUrl: string,
  accessToken: string,
): Promise<void> {
  await fetch(`${baseUrl.replace(/\/+$/, "")}/devices/register`, {
    method: "POST",
    headers: apiHeaders(accessToken),
    body: JSON.stringify({
      device_id: getOrCreateDeviceId(),
      device_type: getDeviceType(),
      label: "Desktop",
    }),
  });
}

export function isSupabaseConfigured(): boolean {
  const url = import.meta.env.VITE_SUPABASE_URL?.trim();
  const key = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();
  return Boolean(url && key);
}
