const DEFAULT_BACKEND = "http://127.0.0.1:8000";

export function formatBackendError(err: unknown, baseUrl: string): string {
  const msg = err instanceof Error ? err.message : String(err);
  if (
    msg === "Failed to fetch" ||
    msg.includes("NetworkError") ||
    msg.toLowerCase().includes("failed to fetch")
  ) {
    return `Cannot reach the backend at ${baseUrl}. The Backend API may not be running — it starts automatically when you finish this step, or you can start it from the main app status bar.`;
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
export async function ensureBackendRunning(maxWaitMs = 45000): Promise<string> {
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
      return baseUrl;
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
