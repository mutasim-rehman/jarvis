import type { HealthResponse } from "./desktop-api";

export type ChatProviderOverride = "huggingface" | "ollama";
export type BotMode = "jarvis_cloud" | "huggingface_cloud" | "local_ollama";

export type ChatbotFallbackMeta = {
  status?: string;
  chatbot_provider?: string;
  reason?: string;
  fallback_options?: Array<{ id?: string; label?: string }>;
};

export type PendingConfirm = {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export function defaultHealthMap(): Record<"backend" | "executor", HealthResponse> {
  return {
    backend: { ok: false, status: 0, error: "Not checked yet" },
    executor: { ok: false, status: 0, error: "Not checked yet" },
  };
}

export function extractAssistantText(data: unknown): string {
  if (typeof data === "string") return data;
  if (!data || typeof data !== "object") return "Received response from backend.";

  const record = data as Record<string, unknown>;

  const executionResult = record.execution_result;
  if (executionResult && typeof executionResult === "object") {
    const results = (executionResult as Record<string, unknown>).results;
    if (Array.isArray(results)) {
      const bestTask = [...results]
        .reverse()
        .find((item) => {
          if (!item || typeof item !== "object") return false;
          const row = item as Record<string, unknown>;
          const message = row.message;
          return typeof message === "string" && message.trim().length > 0;
        });
      if (bestTask && typeof bestTask === "object") {
        const message = (bestTask as Record<string, unknown>).message;
        if (typeof message === "string" && message.trim()) {
          return message;
        }
      }
    }
  }

  const candidateKeys = ["response", "text", "message", "output", "assistant"];
  for (const key of candidateKeys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }

  const nestedAssistant = record.assistant_response;
  if (nestedAssistant && typeof nestedAssistant === "object") {
    const nestedMessage = (nestedAssistant as Record<string, unknown>).message;
    if (typeof nestedMessage === "string" && nestedMessage.trim()) {
      return nestedMessage;
    }
  }
  return JSON.stringify(data, null, 2);
}

export function extractFallbackMeta(data: unknown): ChatbotFallbackMeta | null {
  if (!data || typeof data !== "object") return null;
  const assistantResponse = (data as Record<string, unknown>).assistant_response;
  if (!assistantResponse || typeof assistantResponse !== "object") return null;
  const meta = (assistantResponse as Record<string, unknown>).meta;
  if (!meta || typeof meta !== "object") return null;
  const candidate = meta as ChatbotFallbackMeta;
  if (candidate.status !== "unavailable") return null;
  return candidate;
}
