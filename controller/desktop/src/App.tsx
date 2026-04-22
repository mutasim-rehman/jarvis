import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { HealthResponse, ServiceId, ServiceStatus } from "./desktop-api";
import "./App.css";

type MessageRole = "user" | "assistant" | "system";

interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
}

const healthServiceIds: ServiceId[] = ["backend", "executor"];
const coreServiceIds: ServiceId[] = ["backend", "executor", "cli"];

function formatTime(timestamp: number | null): string {
  if (!timestamp) {
    return "N/A";
  }
  return new Date(timestamp).toLocaleTimeString();
}

function defaultHealthMap() {
  return {
    backend: { ok: false, status: 0, error: "Not checked yet" } satisfies HealthResponse,
    executor: { ok: false, status: 0, error: "Not checked yet" } satisfies HealthResponse,
  };
}

function App() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [health, setHealth] = useState<Record<"backend" | "executor", HealthResponse>>(defaultHealthMap);
  const [chatInput, setChatInput] = useState("");
  const [chatBaseUrl, setChatBaseUrl] = useState("http://127.0.0.1:8000");
  const [chatLoading, setChatLoading] = useState(false);
  const [showDevTools, setShowDevTools] = useState(false);
  const [repoRoot, setRepoRoot] = useState("");
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "boot-message",
      role: "system",
      text: "Launcher ready. Start backend + executor, then send a Jarvis command.",
    },
  ]);

  const servicesById = useMemo(
    () =>
      services.reduce<Record<string, ServiceStatus>>((acc, service) => {
        acc[service.id] = service;
        return acc;
      }, {}),
    [services],
  );
  const runningCoreCount = coreServiceIds.filter((serviceId) => servicesById[serviceId]?.running).length;
  const areAllCoreRunning = coreServiceIds.every((serviceId) => servicesById[serviceId]?.running);

  const refreshServices = async () => {
    const nextServices = await window.desktopApi.listServices();
    setServices(nextServices);
  };

  const refreshHealth = async () => {
    const nextHealth = await Promise.all(
      healthServiceIds.map(async (serviceId) => [serviceId, await window.desktopApi.checkServiceHealth(serviceId)] as const),
    );
    const backendHealth = nextHealth.find(([serviceId]) => serviceId === "backend")?.[1];
    const executorHealth = nextHealth.find(([serviceId]) => serviceId === "executor")?.[1];
    setHealth({
      backend: backendHealth ?? { ok: false, status: 0, error: "Backend health unavailable" },
      executor: executorHealth ?? { ok: false, status: 0, error: "Executor health unavailable" },
    });
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshServices();
      void refreshHealth();
      window.desktopApi
        .getRepoRoot()
        .then(setRepoRoot)
        .catch(() => setRepoRoot("Unable to resolve repo root."));
    }, 0);
    return () => {
      window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    const unsubscribe = window.desktopApi.onServiceLog(({ serviceId, line }) => {
      setServices((previous) =>
        previous.map((service) => {
          if (service.id !== serviceId) {
            return service;
          }
          const nextLogs = [...service.logs, line].slice(-300);
          return { ...service, logs: nextLogs };
        }),
      );
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    const servicesInterval = window.setInterval(() => {
      void refreshServices();
    }, 2500);
    const healthInterval = window.setInterval(() => {
      void refreshHealth();
    }, 3000);

    return () => {
      window.clearInterval(servicesInterval);
      window.clearInterval(healthInterval);
    };
  }, []);

  useEffect(() => {
    const element = messagesRef.current;
    if (!element) {
      return;
    }
    element.scrollTop = element.scrollHeight;
  }, [messages, chatLoading]);

  const runServiceAction = async (action: () => Promise<unknown>) => {
    await action();
    await refreshServices();
    await refreshHealth();
  };

  const handleSend = async (event: FormEvent) => {
    event.preventDefault();
    const text = chatInput.trim();
    if (!text) {
      return;
    }

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text,
    };
    setMessages((previous) => [...previous, userMessage]);
    setChatInput("");
    setChatLoading(true);

    try {
      const result = await window.desktopApi.interactWithBackend(text, chatBaseUrl);

      // Backward-compatible response handling:
      // - New shape from Electron main: { ok: boolean, data?: unknown, error?: string }
      // - Legacy/raw shape: direct backend JSON payload.
      const isWrappedResult =
        typeof result === "object" &&
        result !== null &&
        Object.prototype.hasOwnProperty.call(result, "ok");

      if (isWrappedResult) {
        const wrapped = result as { ok: boolean; data?: unknown; error?: string };
        if (!wrapped.ok) {
          const safeError = wrapped.error || "Unknown backend error";
          setMessages((previous) => [
            ...previous,
            {
              id: `error-${Date.now()}`,
              role: "system",
              text: `Failed to call /api/interact: ${safeError}`,
            },
          ]);
          return;
        }
      }

      let payload: unknown;
      if (isWrappedResult) {
        payload = (result as { data?: unknown }).data;
      } else {
        payload = result;
      }

      const response = payload as {
        assistant_response?: { message?: string };
        execution_result?: { overall_success?: boolean; results?: { action?: string; success?: boolean; message?: string }[] };
      };

      if (!response || typeof response !== "object") {
        setMessages((previous) => [
          ...previous,
          {
            id: `error-${Date.now()}`,
            role: "system",
            text: "Failed to call /api/interact: malformed response",
          },
        ]);
        return;
      }

      const assistantText = response.assistant_response?.message ?? "No assistant message returned.";
      setMessages((previous) => [
        ...previous,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          text: assistantText,
        },
      ]);

      const results = response.execution_result?.results ?? [];
      if (results.length > 0) {
        const summary = results
          .map((result) => `${result.action ?? "UNKNOWN"}: ${result.success ? "ok" : "failed"}${result.message ? ` (${result.message})` : ""}`)
          .join("\n");
        setMessages((previous) => [
          ...previous,
          {
            id: `execution-${Date.now()}`,
            role: "system",
            text: `Execution results\n${summary}`,
          },
        ]);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setMessages((previous) => [
        ...previous,
        {
          id: `error-${Date.now()}`,
          role: "system",
          text: `Failed to call /api/interact: ${message}`,
        },
      ]);
    } finally {
      setChatLoading(false);
      await refreshHealth();
    }
  };

  return (
    <main className="app">
      <header className="hero">
        <div>
          <h1>Jarvis Desktop</h1>
          <p>Press one button to bring Jarvis alive, then chat naturally.</p>
        </div>
        <button className="mini" onClick={() => setShowDevTools((value) => !value)}>
          {showDevTools ? "Hide Dev Tools" : "Dev Tools"}
        </button>
      </header>

      <section className="launcher">
        <div className="launcher-main">
          <button
            className={`launcher-button ${areAllCoreRunning ? "stop" : "start"}`}
            onClick={() =>
              void runServiceAction(() =>
                areAllCoreRunning ? window.desktopApi.stopAllServices() : window.desktopApi.startAllServices(),
              )
            }
          >
            {areAllCoreRunning ? "Stop Jarvis" : "Start Jarvis"}
          </button>
          <p className="launcher-text">
            {runningCoreCount === 0
              ? "All services are stopped."
              : `${runningCoreCount}/3 services running.`}
          </p>
        </div>
        <div className="status-row">
          <span className={`badge ${health.backend.ok ? "ok" : "error"}`}>
            Backend: {health.backend.ok ? "Online" : "Offline"}
          </span>
          <span className={`badge ${health.executor.ok ? "ok" : "error"}`}>
            Executor: {health.executor.ok ? "Online" : "Offline"}
          </span>
        </div>
      </section>

      <section className="chat">
        <header className="chat-header">
          <h2>Messages</h2>
        </header>

        <div className="messages" ref={messagesRef}>
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.role}`}>
              <strong>{message.role}</strong>
              <p>{message.text}</p>
            </div>
          ))}
        </div>

        <form onSubmit={handleSend} className="chat-form">
          <input
            placeholder='Try: "play music", "open chrome", "watch brooklyn 99 clips"'
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            disabled={chatLoading}
          />
          <button type="submit" disabled={chatLoading}>
            {chatLoading ? "Sending..." : "Send"}
          </button>
        </form>
      </section>

      {showDevTools ? (
        <section className="dev-tools">
          <header className="dev-header">
            <h2>Dev Tools</h2>
            <div className="dev-actions">
              <button className="ghost" onClick={() => void runServiceAction(refreshServices)}>
                Refresh
              </button>
              <button onClick={() => void runServiceAction(() => window.desktopApi.startAllServices())}>Start all</button>
              <button className="danger" onClick={() => void runServiceAction(() => window.desktopApi.stopAllServices())}>
                Stop all
              </button>
            </div>
          </header>

          <div className="meta">
            <div>
              <span className="label">Repo root</span>
              <code>{repoRoot || "Loading..."}</code>
            </div>
            <label>
              <span className="label">Backend URL</span>
              <input value={chatBaseUrl} onChange={(event) => setChatBaseUrl(event.target.value)} />
            </label>
            <div>
              <span className="label">Session</span>
              <code>{runningCoreCount === 3 ? "fully active" : "partial / stopped"}</code>
            </div>
          </div>

          <section className="service-grid">
            {services.map((service) => (
              <article key={service.id} className="service-card">
                <header>
                  <h3>{service.name}</h3>
                  <span className={`badge ${service.running ? "ok" : "error"}`}>{service.running ? "Running" : "Stopped"}</span>
                </header>
                <p className="command">{service.command}</p>
                <p className="service-meta">
                  PID: {service.pid ?? "N/A"} | Started: {formatTime(service.startedAt)}
                </p>
                <div className="card-actions">
                  <button onClick={() => void runServiceAction(() => window.desktopApi.startService(service.id))} disabled={service.running}>
                    Start
                  </button>
                  <button
                    className="danger"
                    onClick={() => void runServiceAction(() => window.desktopApi.stopService(service.id))}
                    disabled={!service.running}
                  >
                    Stop
                  </button>
                </div>
                <pre>{(servicesById[service.id]?.logs ?? []).slice(-20).join("\n") || "No logs yet."}</pre>
              </article>
            ))}
          </section>
        </section>
      ) : null}
    </main>
  );
}

export default App;
