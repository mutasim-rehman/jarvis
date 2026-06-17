const DEFAULT_BACKEND = "http://127.0.0.1:8000";

export function formatBackendError(err: unknown, baseUrl: string): string {
  const msg = err instanceof Error ? err.message : String(err);
  if (msg.includes("404") && msg.includes("/auth/me")) {
    return `Backend API was not found at ${baseUrl} (got 404). The app may have connected to the Executor by mistake — restart the desktop app so it can find the correct port.`;
  }
  if (
    msg.includes("503") ||
    msg.toLowerCase().includes("database") ||
    msg.toLowerCase().includes("getaddrinfo") ||
    msg.toLowerCase().includes("failed to resolve host")
  ) {
    return `Cannot reach the database for account setup. In Supabase → Project Settings → Database, copy the Session pooler URI (port 5432) into DATABASE_URL in your repo .env, then restart the app. (${msg})`;
  }
  if (msg.includes("500") && msg.includes("/auth/me")) {
    return `Account lookup failed (500). This usually means an old Backend API is still running on port 8000. Stop all Python/uvicorn processes, restart the desktop app (npm run dev), then try again. (${msg})`;
  }
  if (
    msg === "Failed to fetch" ||
    msg.includes("NetworkError") ||
    msg.toLowerCase().includes("failed to fetch")
  ) {
    return `Cannot reach the backend at ${baseUrl}. JARVIS is starting the Backend API automatically — this can take up to a minute on first launch. If the problem persists, restart the app and ensure Python dependencies are installed (see controller/desktop/README.md).`;
  }
  return msg;
}

export async function resolveBackendBaseUrl(): Promise<string> {
  if (typeof window !== "undefined" && window.desktopApi?.getServiceBaseUrl) {
    const url = await window.desktopApi.getServiceBaseUrl("backend");
    return url?.trim() || DEFAULT_BACKEND;
  }
  return DEFAULT_BACKEND;
}

/** Start backend via Electron if needed and wait until /health responds. */
export async function ensureBackendRunning(maxWaitMs = 90000): Promise<string> {
  const baseUrl = await resolveBackendBaseUrl();
  const api = typeof window !== "undefined" ? window.desktopApi : undefined;
  if (!api?.checkServiceHealth || !api.startService) {
    return baseUrl;
  }

  let startAttempted = false;
  const deadline = Date.now() + maxWaitMs;

  while (Date.now() < deadline) {
    const health = await api.checkServiceHealth("backend");
    if (health.ok) {
      return await resolveBackendBaseUrl();
    }
    if (!startAttempted) {
      startAttempted = true;
      try {
        await api.startService("backend");
      } catch {
        // May already be starting or port in use with a healthy instance
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 800));
  }

  throw new Error(formatBackendError(new Error("Failed to fetch"), baseUrl));
}
