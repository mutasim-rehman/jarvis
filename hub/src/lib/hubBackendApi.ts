const DEVICE_KEY = "jarvis_device_id";

export function getOrCreateDeviceId(): string {
  if (typeof localStorage === "undefined") {
    return "";
  }
  const existing = localStorage.getItem(DEVICE_KEY);
  if (existing) {
    return existing;
  }
  const id = crypto.randomUUID();
  localStorage.setItem(DEVICE_KEY, id);
  return id;
}

function backendBase(): string {
  return (import.meta.env.PUBLIC_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
}

function headers(token: string): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    "X-Device-Id": getOrCreateDeviceId(),
  };
}

export async function fetchAuthMe(token: string) {
  const res = await fetch(`${backendBase()}/auth/me`, { headers: headers(token) });
  if (!res.ok) {
    throw new Error(`auth/me ${res.status}`);
  }
  return res.json();
}

export async function patchPreferences(token: string, body: Record<string, unknown>) {
  const res = await fetch(`${backendBase()}/preferences`, {
    method: "PATCH",
    headers: headers(token),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`preferences ${res.status}`);
  }
  return res.json();
}

export async function fetchPersonalityTemplate(token: string) {
  const res = await fetch(`${backendBase()}/preferences/personality/template`, {
    headers: headers(token),
  });
  if (!res.ok) {
    throw new Error(`template ${res.status}`);
  }
  return res.json();
}

export async function importPersonality(token: string, doc: unknown) {
  const res = await fetch(`${backendBase()}/preferences/personality`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(doc),
  });
  if (!res.ok) {
    throw new Error(`personality ${res.status}`);
  }
  return res.json();
}
