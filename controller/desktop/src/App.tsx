import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { HealthResponse, ServiceId, ServiceStatus, TerminalSnapshot } from "./desktop-api";
import "./AppClean.css";
import { JarvisHUD } from "./JarvisHUD";

const healthServiceIds: ServiceId[] = ["backend", "executor"];
const coreServiceIds: ServiceId[] = ["backend", "executor", "cli"];
const backendBaseUrl = "http://127.0.0.1:8000";

type ConversationRole = "user" | "assistant" | "system";
type ConversationMessage = {
  id: string;
  role: ConversationRole;
  text: string;
};

type BrowserSpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: Event & { resultIndex: number; results: SpeechRecognitionResultList }) => void) | null;
  onerror: ((event: Event) => void) | null;
  onend: (() => void) | null;
};

type BrowserSpeechRecognitionCtor = new () => BrowserSpeechRecognition;

function defaultHealthMap() {
  return {
    backend: { ok: false, status: 0, error: "Not checked yet" } satisfies HealthResponse,
    executor: { ok: false, status: 0, error: "Not checked yet" } satisfies HealthResponse,
  };
}

function extractAssistantText(data: unknown): string {
  if (typeof data === "string") return data;
  if (!data || typeof data !== "object") return "Received response from backend.";

  const record = data as Record<string, unknown>;
  const candidateKeys = ["response", "text", "message", "output", "assistant"];
  for (const key of candidateKeys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return JSON.stringify(data, null, 2);
}

export default function App() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [health, setHealth] = useState<Record<"backend" | "executor", HealthResponse>>(defaultHealthMap);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [micOn, setMicOn] = useState(false);
  const [speakModeOn, setSpeakModeOn] = useState(false);
  const [terminalsOpen, setTerminalsOpen] = useState(false);
  const [terminalsLoading, setTerminalsLoading] = useState(false);
  const [terminals, setTerminals] = useState<TerminalSnapshot[]>([]);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const speakingModeRef = useRef(false);

  const servicesById = useMemo(
    () => services.reduce<Record<string, ServiceStatus>>((acc, service) => {
      acc[service.id] = service;
      return acc;
    }, {}),
    [services]
  );
  
  const areAllCoreRunning = coreServiceIds.every((id) => servicesById[id]?.running);
  const runningTerminals = terminals.filter((terminal) => terminal.lastExitCode === "" || terminal.lastExitCode === "null");

  const refreshServices = useCallback(async () => {
    const next = await window.desktopApi.listServices();
    setServices(next);
  }, []);

  const refreshHealth = useCallback(async () => {
    const nextHealth = await Promise.all(
      healthServiceIds.map(async (id) => [id, await window.desktopApi.checkServiceHealth(id)] as const)
    );
    const backend = nextHealth.find(([id]) => id === "backend")?.[1];
    const executor = nextHealth.find(([id]) => id === "executor")?.[1];
    setHealth({
      backend: backend ?? { ok: false, status: 0, error: "Backend health unavailable" },
      executor: executor ?? { ok: false, status: 0, error: "Executor health unavailable" },
    });
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshServices(), refreshHealth()]);
  }, [refreshHealth, refreshServices]);

  const addMessage = useCallback((role: ConversationRole, text: string) => {
    const payload = text.trim();
    if (!payload) return;
    setMessages((previous) => [
      ...previous,
      {
        id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        role,
        text: payload,
      },
    ]);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshAll();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [refreshAll]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void refreshAll();
    }, 5000);

    return () => {
      window.clearInterval(interval);
    };
  }, [refreshAll]);

  const runServiceAction = async (action: () => Promise<unknown>) => {
    await action();
    await refreshAll();
  };

  const speakAssistant = useCallback((text: string) => {
    if (!text.trim() || !("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.02;
    utterance.pitch = 1.0;
    utterance.lang = "en-US";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }, []);

  const sendText = useCallback(async (raw: string) => {
    const text = raw.trim();
    if (!text) return;
    addMessage("user", text);
    setChatLoading(true);
    try {
      const result = await window.desktopApi.interactWithBackend(text, backendBaseUrl);
      if ("error" in result) {
        addMessage("system", `Backend error: ${result.error}`);
        return;
      }
      const reply = extractAssistantText(result.data);
      addMessage("assistant", reply);
      if (speakModeOn) {
        speakAssistant(reply);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unknown request error";
      addMessage("system", message);
    } finally {
      setChatLoading(false);
      await refreshHealth();
    }
  }, [addMessage, refreshHealth, speakAssistant, speakModeOn]);

  const stopMicRecognition = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.onend = null;
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
  }, []);

  const startMicRecognition = useCallback(() => {
    const speechCtor = (
      window as typeof window & {
        SpeechRecognition?: BrowserSpeechRecognitionCtor;
        webkitSpeechRecognition?: BrowserSpeechRecognitionCtor;
      }
    ).SpeechRecognition
      ?? (
        window as typeof window & {
          SpeechRecognition?: BrowserSpeechRecognitionCtor;
          webkitSpeechRecognition?: BrowserSpeechRecognitionCtor;
        }
      ).webkitSpeechRecognition;

    if (!speechCtor) {
      addMessage("system", "Speech recognition is not available in this runtime.");
      setMicOn(false);
      return;
    }

    const recognition = new speechCtor();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (result.isFinal) {
          const transcript = result[0]?.transcript?.trim() ?? "";
          if (transcript) {
            void sendText(transcript);
          }
        }
      }
    };
    recognition.onerror = () => {
      addMessage("system", "Mic capture error. Try toggling mic again.");
    };
    recognition.onend = () => {
      if (micOn && speakingModeRef.current) {
        recognition.start();
        return;
      }
      recognitionRef.current = null;
    };
    recognition.start();
    recognitionRef.current = recognition;
  }, [addMessage, micOn, sendText]);

  useEffect(() => {
    speakingModeRef.current = speakModeOn;
  }, [speakModeOn]);

  useEffect(() => {
    if (micOn) {
      startMicRecognition();
      return;
    }
    stopMicRecognition();
  }, [micOn, startMicRecognition, stopMicRecognition]);

  useEffect(() => () => {
    stopMicRecognition();
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }, [stopMicRecognition]);

  const loadTerminals = async () => {
    setTerminalsLoading(true);
    const response = await window.desktopApi.listTerminals();
    setTerminalsLoading(false);
    if ("error" in response) {
      addMessage("system", `Terminals unavailable: ${response.error}`);
      return;
    }
    setTerminals(response.data);
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    await sendText(chatInput);
    setChatInput("");
  };

  return (
    <main className={`app ${speakModeOn ? "speak-mode" : ""}`}>
      <div className="top-bar">
        <button
          type="button"
          onClick={() =>
            void runServiceAction(() =>
              areAllCoreRunning ? window.desktopApi.stopAllServices() : window.desktopApi.startAllServices()
            )
          }
        >
          {areAllCoreRunning ? "Stop Jarvis" : "Start Jarvis"}
        </button>
        <button type="button" onClick={() => void refreshAll()}>
          Refresh
        </button>
        <button
          type="button"
          onClick={() => {
            if (!terminalsOpen) {
              void loadTerminals();
            }
            setTerminalsOpen((value) => !value);
          }}
        >
          Terminals
        </button>
        <button type="button" onClick={() => void window.desktopApi.openDevTools()}>
          DevTools
        </button>
        <span className={`badge ${health.backend.ok ? "ok" : "error"}`}>
          Backend: {health.backend.ok ? "Online" : "Offline"}
        </span>
        <span className={`badge ${health.executor.ok ? "ok" : "error"}`}>
          Executor: {health.executor.ok ? "Online" : "Offline"}
        </span>
      </div>

      {terminalsOpen ? (
        <section className="terminals-panel">
          <header>
            <h3>Running Terminals</h3>
            <button type="button" onClick={() => void loadTerminals()} disabled={terminalsLoading}>
              {terminalsLoading ? "Refreshing..." : "Refresh list"}
            </button>
          </header>
          <div className="terminal-items">
            {runningTerminals.length === 0 ? (
              <p className="terminal-empty">No running terminals found.</p>
            ) : (
              runningTerminals.map((terminal) => (
                <article key={terminal.id} className="terminal-item">
                  <strong>#{terminal.id}</strong>
                  <span>{terminal.cwd || "(cwd unavailable)"}</span>
                  <code>{terminal.lastCommand || "(no command recorded)"}</code>
                </article>
              ))
            )}
          </div>
        </section>
      ) : null}

      <section className={`layout ${speakModeOn ? "layout-speak" : ""}`}>
        <div className="visual-pane">
          <div className="visual-shell">
            <JarvisHUD />
          </div>
        </div>

        <aside className={`conversation-pane ${speakModeOn ? "hidden" : ""}`}>
          <h2>Jarvis Conversation</h2>
          <div className="messages">
            {messages.length === 0 ? (
              <p className="empty">No conversation yet.</p>
            ) : (
              messages.map((message) => (
                <article key={message.id} className={`message ${message.role}`}>
                  <strong>{message.role}</strong>
                  <p>{message.text}</p>
                </article>
              ))
            )}
          </div>
          <form className="chat-controls" onSubmit={handleSend}>
            <input
              placeholder="Enter command..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              disabled={chatLoading}
            />
            <button type="submit" disabled={chatLoading}>
              {chatLoading ? "Sending..." : "Send"}
            </button>
            <button type="button" className={micOn ? "active" : ""} onClick={() => setMicOn((value) => !value)}>
              {micOn ? "Mic On" : "Mic"}
            </button>
            <button
              type="button"
              className={speakModeOn ? "active" : ""}
              onClick={() => {
                setSpeakModeOn((value) => !value);
                if (speakModeOn) {
                  window.speechSynthesis.cancel();
                }
              }}
            >
              {speakModeOn ? "Speak On" : "Speak"}
            </button>
          </form>
        </aside>
      </section>

      {speakModeOn ? (
        <button
          type="button"
          className="speak-floating"
          onClick={() => {
            setSpeakModeOn(false);
            window.speechSynthesis.cancel();
          }}
        >
          Speak Off
        </button>
      ) : null}
    </main>
  );
}
