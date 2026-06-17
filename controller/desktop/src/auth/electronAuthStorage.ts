import type { SupportedStorage } from "@supabase/supabase-js";

function canUseElectronAuthStorage(): boolean {
  const api = typeof window !== "undefined" ? window.desktopApi : undefined;
  return Boolean(
    api &&
      "authStorageGetItem" in api &&
      "authStorageSetItem" in api &&
      "authStorageRemoveItem" in api,
  );
}

/** Persist Supabase auth tokens in Electron userData (survives app restarts). */
export function createElectronAuthStorage(): SupportedStorage | null {
  if (!canUseElectronAuthStorage()) {
    return null;
  }
  const api = window.desktopApi;

  return {
    getItem: async (key: string) => {
      const stored = await api.authStorageGetItem(key);
      if (stored !== null) {
        return stored;
      }
      try {
        const legacy = localStorage.getItem(key);
        if (legacy) {
          await api.authStorageSetItem(key, legacy);
          return legacy;
        }
      } catch {
        // localStorage unavailable
      }
      return null;
    },
    setItem: async (key: string, value: string) => {
      await api.authStorageSetItem(key, value);
      try {
        localStorage.setItem(key, value);
      } catch {
        // best-effort mirror
      }
    },
    removeItem: async (key: string) => {
      await api.authStorageRemoveItem(key);
      try {
        localStorage.removeItem(key);
      } catch {
        // ignore
      }
    },
  };
}
