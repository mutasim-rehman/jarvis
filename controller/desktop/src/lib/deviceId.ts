const STORAGE_KEY = "jarvis_device_id";

export function getOrCreateDeviceId(): string {
  const existing = localStorage.getItem(STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const id = crypto.randomUUID();
  localStorage.setItem(STORAGE_KEY, id);
  return id;
}

export function getDeviceType(): "laptop" | "phone" | "pi" {
  return "laptop";
}
