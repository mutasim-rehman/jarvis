// Updated App.tsx - simplified UI with HUD background
import { useEffect, useMemo, useState } from "react";
import type { HealthResponse, ServiceId, ServiceStatus } from "./desktop-api";
import "./App.css";
import "./AppClean.css";
import { JarvisHUD } from "./JarvisHUD";

const healthServiceIds: ServiceId[] = ["backend", "executor"];
const coreServiceIds: ServiceId[] = ["backend", "executor", "cli"];

function defaultHealthMap() {
  return {
    backend: { ok: false, status: 0, error: "Not checked yet" } satisfies HealthResponse,
    executor: { ok: false, status: 0, error: "Not checked yet" } satisfies HealthResponse,
  };
}

export default function App() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [health, setHealth] = useState<Record<"backend" | "executor", HealthResponse>>(defaultHealthMap);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  const servicesById = useMemo(
    () => services.reduce<Record<string, ServiceStatus>>((acc, service) => {
      acc[service.id] = service;
      return acc;
    }, {}),
    [services]
  );
  
  const areAllCoreRunning = coreServiceIds.every((id) => servicesById[id]?.running);

  const refreshServices = async () => {
    const next = await window.desktopApi.listServices();
    setServices(next);
  };
  const refreshHealth = async () => {
    const nextHealth = await Promise.all(
      healthServiceIds.map(async (id) => [id, await window.desktopApi.checkServiceHealth(id)] as const)
    );
    const backend = nextHealth.find(([id]) => id === "backend")?.[1];
    const executor = nextHealth.find(([id]) => id === "executor")?.[1];
    setHealth({
      backend: backend ?? { ok: false, status: 0, error: "Backend health unavailable" },
      executor: executor ?? { ok: false, status: 0, error: "Executor health unavailable" },
    });
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshServices();
      void refreshHealth();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void refreshServices();
      void refreshHealth();
    }, 5000);

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  const runServiceAction = async (action: () => Promise<unknown>) => {
    await action();
    await refreshServices();
    await refreshHealth();
  };

  const sendText = async (raw: string) => {
    const text = raw.trim();
    if (!text) return;
    setChatLoading(true);
    try {
      const result = await window.desktopApi.interactWithBackend(text, "http://127.0.0.1:8000");
      if ("error" in result) {
        console.error("Backend error:", result.error);
        return;
      }
      console.log("Backend response:", result.data);
    } catch (e) {
      console.error(e);
    } finally {
      setChatLoading(false);
      await refreshHealth();
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    await sendText(chatInput);
    setChatInput("");
  };

  return (
    <main className="app">
      <JarvisHUD />
      <div className="control-panel">
        <button
          onClick={() =>
            void runServiceAction(() =>
              areAllCoreRunning ? window.desktopApi.stopAllServices() : window.desktopApi.startAllServices()
            )
          }
        >
          {areAllCoreRunning ? "Stop Jarvis" : "Start Jarvis"}
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
      <form className="chat-input-bar" onSubmit={handleSend}>
        <input
          placeholder="Enter command..."
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          disabled={chatLoading}
        />
        <button type="submit" disabled={chatLoading}>
          {chatLoading ? "Sending..." : "Send"}
        </button>
      </form>
    </main>
  );
}
