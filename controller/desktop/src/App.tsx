import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { HealthResponse, JarvisProfile, ServiceId, ServiceStatus } from "./desktop-api";
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

function floatTo16BitPCM(samples: Float32Array): Int16Array {
  const pcm = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i += 1) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return pcm;
}

function downsampleBuffer(buffer: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (inputRate === outputRate) {
    return buffer;
  }
  const ratio = inputRate / outputRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i += 1) {
      accum += buffer[i];
      count += 1;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

function mergeChunks(chunks: Float32Array[]): Float32Array {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const merged = new Float32Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function wavFromFloat32(samples: Float32Array, sampleRate: number): Uint8Array {
  const pcm = floatTo16BitPCM(samples);
  const bytesPerSample = 2;
  const dataSize = pcm.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  const writeString = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i));
    }
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (let i = 0; i < pcm.length; i += 1) {
    view.setInt16(offset, pcm[i], true);
    offset += 2;
  }

  return new Uint8Array(buffer);
}

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

function App() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [health, setHealth] = useState<Record<"backend" | "executor", HealthResponse>>(defaultHealthMap);
  const [chatInput, setChatInput] = useState("");
  const [chatBaseUrl, setChatBaseUrl] = useState("http://127.0.0.1:8000");
  const [chatLoading, setChatLoading] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [speechIssue, setSpeechIssue] = useState<string | null>(null);
  const [jarvisProfile, setJarvisProfile] = useState<JarvisProfile | null>(null);
  const [showDevTools, setShowDevTools] = useState(false);
  const [repoRoot, setRepoRoot] = useState("");
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const lastSpeechErrorRef = useRef<string | null>(null);
  const ttsErrorRef = useRef<string | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const audioChunksRef = useRef<Float32Array[]>([]);
  const inputSampleRateRef = useRef<number>(44100);
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
  const speechToTextSupported = Boolean(window.navigator.mediaDevices?.getUserMedia);

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

      window.desktopApi
        .getJarvisProfile()
        .then((profileResult) => {
          if (!profileResult.ok) {
            return;
          }
          setJarvisProfile(profileResult.data);
          const greeting = profileResult.data.interaction_rules?.greetings?.[0];
          if (greeting) {
            setMessages((previous) =>
              previous.map((message) =>
                message.id === "boot-message"
                  ? {
                      ...message,
                      text: `${greeting} Start Jarvis when ready, then tell me what to do.`,
                    }
                  : message,
              ),
            );
          }
        })
        .catch(() => undefined);
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

  useEffect(() => {
    if (voiceEnabled) {
      return;
    }
    window.speechSynthesis.cancel();
    currentAudioRef.current?.pause();
    currentAudioRef.current = null;
  }, [voiceEnabled]);

  useEffect(() => {
    return () => {
      void stopAudioPipeline();
      window.speechSynthesis.cancel();
      currentAudioRef.current?.pause();
      currentAudioRef.current = null;
    };
  }, []);

  const runServiceAction = async (action: () => Promise<unknown>) => {
    await action();
    await refreshServices();
    await refreshHealth();
  };

  const speakAssistantText = (text: string) => {
    if (!voiceEnabled || !text || !("speechSynthesis" in window)) {
      return;
    }

    const fallbackBrowserSpeech = () => {
      const utterance = new SpeechSynthesisUtterance(text);
      const speed = jarvisProfile?.voice_profile?.speed;
      utterance.rate = typeof speed === "number" ? speed : 0.95;
      utterance.pitch = jarvisProfile?.voice_profile?.pitch === "medium_low" ? 0.9 : 1;

      const voices = window.speechSynthesis.getVoices();
      const preferredVoice =
        voices.find((voice) => /en-GB/i.test(voice.lang) && /male|david|george|ryan|daniel/i.test(voice.name)) ??
        voices.find((voice) => /en-GB/i.test(voice.lang)) ??
        voices.find((voice) => /en-US/i.test(voice.lang));
      if (preferredVoice) {
        utterance.voice = preferredVoice;
      }

      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    };

    void (async () => {
      const ttsResult = await window.desktopApi.synthesizeSpeech(text, chatBaseUrl);
      if (!ttsResult.ok) {
        const error = "error" in ttsResult ? ttsResult.error : "Unknown Kokoro TTS error";
        if (ttsErrorRef.current !== error) {
          appendSystemMessage(`Kokoro TTS unavailable, falling back to browser voice. ${error}`);
          ttsErrorRef.current = error;
        }
        fallbackBrowserSpeech();
        return;
      }

      const audioBase64 = ttsResult.data.audio_base64;
      if (!audioBase64) {
        fallbackBrowserSpeech();
        return;
      }

      ttsErrorRef.current = null;
      window.speechSynthesis.cancel();
      currentAudioRef.current?.pause();
      currentAudioRef.current = null;

      const audio = new Audio(`data:audio/wav;base64,${audioBase64}`);
      currentAudioRef.current = audio;
      try {
        await audio.play();
      } catch {
        fallbackBrowserSpeech();
      }
    })();
  };

  const appendSystemMessage = (text: string) => {
    setMessages((previous) => [
      ...previous,
      {
        id: `system-${Date.now()}`,
        role: "system",
        text,
      },
    ]);
  };

  const speechErrorMessage = (code?: string) => {
    switch (code) {
      case "not-allowed":
      case "service-not-allowed":
        return "Microphone access is blocked. Please allow microphone permission for this app.";
      case "audio-capture":
        return "No microphone input detected. Please check your selected microphone device.";
      case "no-speech":
        return "I did not catch that. Please speak clearly and try again.";
      case "transcribe-empty":
        return "I did not hear enough audio. Please speak a little longer.";
      case "transcribe-failed":
        return "Offline transcription failed. Make sure the backend and local Vosk model are available.";
      default:
        return `Speech recognition error: ${code || "unknown"}`;
    }
  };

  async function stopAudioPipeline() {
    try {
      processorNodeRef.current?.disconnect();
      sourceNodeRef.current?.disconnect();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        await audioContextRef.current.close();
      }
    } catch {
      // Ignore teardown errors; we just want resources released.
    } finally {
      processorNodeRef.current = null;
      sourceNodeRef.current = null;
      streamRef.current = null;
      audioContextRef.current = null;
    }
  }

  const sendText = async (rawText: string) => {
    const text = rawText.trim();
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
          appendSystemMessage(`Failed to call /api/interact: ${safeError}`);
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
        appendSystemMessage("Failed to call /api/interact: malformed response");
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
      speakAssistantText(assistantText);

      const results = response.execution_result?.results ?? [];
      if (results.length > 0) {
        const summary = results
          .map((result) => `${result.action ?? "UNKNOWN"}: ${result.success ? "ok" : "failed"}${result.message ? ` (${result.message})` : ""}`)
          .join("\n");
        appendSystemMessage(`Execution results\n${summary}`);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      appendSystemMessage(`Failed to call /api/interact: ${message}`);
    } finally {
      setChatLoading(false);
      await refreshHealth();
    }
  };

  const startOfflineListening = async () => {
    if (!speechToTextSupported) {
      appendSystemMessage("Speech-to-text is not supported in this environment.");
      return;
    }

    try {
      const stream = await window.navigator.mediaDevices.getUserMedia({ audio: true });
      const AudioContextCtor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextCtor) {
        throw new Error("audio-context-unavailable");
      }

      const context = new AudioContextCtor();
      inputSampleRateRef.current = context.sampleRate;
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      audioChunksRef.current = [];

      processor.onaudioprocess = (event) => {
        const channel = event.inputBuffer.getChannelData(0);
        audioChunksRef.current.push(new Float32Array(channel));
      };

      source.connect(processor);
      processor.connect(context.destination);

      streamRef.current = stream;
      audioContextRef.current = context;
      sourceNodeRef.current = source;
      processorNodeRef.current = processor;
      setSpeechIssue(null);
      lastSpeechErrorRef.current = null;
      setIsListening(true);
    } catch (error) {
      const code = error instanceof Error ? error.message : "audio-capture";
      const message = speechErrorMessage(code === "audio-context-unavailable" ? "audio-capture" : "not-allowed");
      setSpeechIssue(message);
      appendSystemMessage(message);
    }
  };

  const stopOfflineListening = async () => {
    if (!isListening) {
      return;
    }
    setIsListening(false);
    await stopAudioPipeline();

    const merged = mergeChunks(audioChunksRef.current);
    audioChunksRef.current = [];
    if (merged.length < 4000) {
      const message = speechErrorMessage("transcribe-empty");
      setSpeechIssue(message);
      if (lastSpeechErrorRef.current !== message) {
        appendSystemMessage(message);
        lastSpeechErrorRef.current = message;
      }
      return;
    }

    const downsampled = downsampleBuffer(merged, inputSampleRateRef.current, 16000);
    const wav = wavFromFloat32(downsampled, 16000);
    const base64Audio = toBase64(wav);

    const result = await window.desktopApi.transcribeAudio(base64Audio, chatBaseUrl);
    if (!result.ok) {
      const detail = "error" in result ? result.error : "Unknown transcription error";
      const message = `${speechErrorMessage("transcribe-failed")} ${detail}`;
      setSpeechIssue(message);
      if (lastSpeechErrorRef.current !== message) {
        appendSystemMessage(message);
        lastSpeechErrorRef.current = message;
      }
      return;
    }

    const transcript = (result.data.text || "").trim();
    if (!transcript) {
      const message = speechErrorMessage("no-speech");
      setSpeechIssue(message);
      if (lastSpeechErrorRef.current !== message) {
        appendSystemMessage(message);
        lastSpeechErrorRef.current = message;
      }
      return;
    }

    setSpeechIssue(null);
    lastSpeechErrorRef.current = null;
    setChatInput(transcript);
    await sendText(transcript);
  };

  const toggleListening = () => {
    if (isListening) {
      void stopOfflineListening();
      return;
    }
    void startOfflineListening();
  };

  const handleSend = async (event: FormEvent) => {
    event.preventDefault();
    await sendText(chatInput);
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
          <div className="voice-controls">
            <button className="ghost" onClick={() => setVoiceEnabled((value) => !value)} type="button">
              {voiceEnabled ? "Voice On" : "Voice Off"}
            </button>
            <button
              type="button"
              onClick={toggleListening}
              disabled={!speechToTextSupported || chatLoading}
              className={isListening ? "danger" : "ghost"}
            >
              {isListening ? "Stop Mic" : "Speak"}
            </button>
          </div>
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
        {!speechToTextSupported ? <p className="hint">Speech-to-text is unavailable in this environment.</p> : null}
        {speechToTextSupported && speechIssue ? <p className="hint">{speechIssue}</p> : null}
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
