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
type LocalMicState = {
  stream: MediaStream;
  context: AudioContext;
  source: MediaStreamAudioSourceNode;
  processor: ScriptProcessorNode;
  sink: GainNode;
  chunks: Float32Array[];
  sampleCount: number;
  rmsSum: number;
  rmsFrames: number;
};

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

  const nestedAssistant = record.assistant_response;
  if (nestedAssistant && typeof nestedAssistant === "object") {
    const nestedMessage = (nestedAssistant as Record<string, unknown>).message;
    if (typeof nestedMessage === "string" && nestedMessage.trim()) {
      return nestedMessage;
    }
  }
  return JSON.stringify(data, null, 2);
}

function mergeFloat32Chunks(chunks: Float32Array[], totalLength: number): Float32Array {
  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function downsampleTo16BitPcm(
  input: Float32Array,
  inputSampleRate: number,
  outputSampleRate = 16000
): Int16Array {
  if (input.length === 0) {
    return new Int16Array(0);
  }

  if (inputSampleRate === outputSampleRate) {
    const pcm = new Int16Array(input.length);
    for (let i = 0; i < input.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, input[i]));
      pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
    return pcm;
  }

  const ratio = inputSampleRate / outputSampleRate;
  const outputLength = Math.max(1, Math.floor(input.length / ratio));
  const pcm = new Int16Array(outputLength);
  let outputIndex = 0;
  let inputIndex = 0;

  while (outputIndex < outputLength) {
    const nextInputIndex = Math.min(input.length, Math.round((outputIndex + 1) * ratio));
    let sum = 0;
    let count = 0;
    for (let i = inputIndex; i < nextInputIndex; i += 1) {
      sum += input[i];
      count += 1;
    }
    const averaged = count > 0 ? sum / count : input[Math.min(inputIndex, input.length - 1)];
    const sample = Math.max(-1, Math.min(1, averaged));
    pcm[outputIndex] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    outputIndex += 1;
    inputIndex = nextInputIndex;
  }

  return pcm;
}

function wavBase64FromPcm16(pcm: Int16Array, sampleRate: number): string {
  const buffer = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(buffer);
  const writeText = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i));
    }
  };

  writeText(0, "RIFF");
  view.setUint32(4, 36 + pcm.length * 2, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, pcm.length * 2, true);

  let offset = 44;
  for (let i = 0; i < pcm.length; i += 1) {
    view.setInt16(offset, pcm[i], true);
    offset += 2;
  }

  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return window.btoa(binary);
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
  const micOnRef = useRef(false);
  const micNetworkIssueNotifiedRef = useRef(false);
  const useLocalMicRef = useRef(false);
  const localMicStateRef = useRef<LocalMicState | null>(null);
  const localMicInitializingRef = useRef(false);
  const localTranscribeBusyRef = useRef(false);

  const servicesById = useMemo(
    () => services.reduce<Record<string, ServiceStatus>>((acc, service) => {
      acc[service.id] = service;
      return acc;
    }, {}),
    [services]
  );
  
  const areAllCoreRunning = coreServiceIds.every((id) => servicesById[id]?.running);
  const runningTerminals = terminals.filter((terminal) => {
    if (terminal.activeCommand.trim()) return true;
    return terminal.lastExitCode === "" || terminal.lastExitCode === "null";
  });

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

  const stopLocalMicCapture = useCallback(() => {
    const state = localMicStateRef.current;
    if (!state) return;
    state.processor.onaudioprocess = null;
    state.source.disconnect();
    state.processor.disconnect();
    state.sink.disconnect();
    state.stream.getTracks().forEach((track) => track.stop());
    void state.context.close();
    localMicStateRef.current = null;
    localMicInitializingRef.current = false;
  }, []);

  const transcribeLocalSegment = useCallback(async (audio: Float32Array, inputSampleRate: number) => {
    if (localTranscribeBusyRef.current) {
      return;
    }
    const pcm = downsampleTo16BitPcm(audio, inputSampleRate, 16000);
    if (pcm.length < 8000) {
      return;
    }

    localTranscribeBusyRef.current = true;
    try {
      const wavBase64 = wavBase64FromPcm16(pcm, 16000);
      const response = await window.desktopApi.transcribeAudio(wavBase64, backendBaseUrl);
      if ("error" in response) {
        addMessage("system", `Transcription error: ${response.error}`);
        return;
      }
      const transcript = (response.data.text ?? "").trim();
      if (transcript) {
        void sendText(transcript);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown transcription failure";
      addMessage("system", `Transcription error: ${message}`);
    } finally {
      localTranscribeBusyRef.current = false;
    }
  }, [addMessage, sendText]);

  const startLocalMicCapture = useCallback(async () => {
    if (localMicStateRef.current || localMicInitializingRef.current) return;
    localMicInitializingRef.current = true;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      const context = new AudioContext();
      await context.resume();

      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      const sink = context.createGain();
      sink.gain.value = 0;

      const state: LocalMicState = {
        stream,
        context,
        source,
        processor,
        sink,
        chunks: [],
        sampleCount: 0,
        rmsSum: 0,
        rmsFrames: 0,
      };

      processor.onaudioprocess = (event) => {
        if (!micOnRef.current) return;
        const chunk = new Float32Array(event.inputBuffer.getChannelData(0));
        state.chunks.push(chunk);
        state.sampleCount += chunk.length;

        let energy = 0;
        for (let i = 0; i < chunk.length; i += 1) {
          energy += chunk[i] * chunk[i];
        }
        const rms = Math.sqrt(energy / chunk.length);
        state.rmsSum += rms;
        state.rmsFrames += 1;

        const segmentSeconds = state.sampleCount / state.context.sampleRate;
        if (segmentSeconds < 3.0) return;

        const avgRms = state.rmsFrames ? state.rmsSum / state.rmsFrames : 0;
        const merged = mergeFloat32Chunks(state.chunks, state.sampleCount);
        state.chunks = [];
        state.sampleCount = 0;
        state.rmsSum = 0;
        state.rmsFrames = 0;

        if (avgRms > 0.011) {
          void transcribeLocalSegment(merged, state.context.sampleRate);
        }
      };

      source.connect(processor);
      processor.connect(sink);
      sink.connect(context.destination);
      localMicStateRef.current = state;
      localMicInitializingRef.current = false;
      if (!micNetworkIssueNotifiedRef.current) {
        addMessage("system", "Mic switched to local transcription mode.");
        micNetworkIssueNotifiedRef.current = true;
      }
    } catch (error) {
      localMicInitializingRef.current = false;
      const message = error instanceof Error ? error.message : "Unable to access microphone";
      addMessage("system", `Mic access error: ${message}`);
      setMicOn(false);
    }
  }, [addMessage, transcribeLocalSegment]);

  const startMicRecognition = useCallback(() => {
    if (recognitionRef.current) return;
    if (useLocalMicRef.current) {
      if (!localMicStateRef.current) {
        void startLocalMicCapture();
      }
      return;
    }

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
      useLocalMicRef.current = true;
      void startLocalMicCapture();
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
    recognition.onerror = (event) => {
      const errorType = (event as Event & { error?: string }).error ?? "";
      if (errorType === "aborted" || errorType === "no-speech") {
        return;
      }
      if (errorType === "network") {
        useLocalMicRef.current = true;
        if (!micNetworkIssueNotifiedRef.current) {
          addMessage("system", "Mic recognition network issue detected. Switching to local transcription...");
          micNetworkIssueNotifiedRef.current = true;
        }
        try {
          recognition.stop();
        } catch {
          // Ignore stop failures before forced restart.
        }
        return;
      }
      addMessage("system", `Mic capture error${errorType ? ` (${errorType})` : ""}.`);
    };
    recognition.onend = () => {
      if (useLocalMicRef.current) {
        recognitionRef.current = null;
        if (micOnRef.current) {
          void startLocalMicCapture();
        }
        return;
      }
      if (micOnRef.current) {
        window.setTimeout(() => {
          if (!micOnRef.current || recognitionRef.current !== recognition) {
            return;
          }
          try {
            recognition.start();
          } catch {
            // Ignore transient restart failures; next state transition restarts recognition.
          }
        }, 180);
        return;
      }
      recognitionRef.current = null;
    };
    recognition.start();
    recognitionRef.current = recognition;
  }, [addMessage, sendText, startLocalMicCapture]);

  useEffect(() => {
    micOnRef.current = micOn;
    if (!micOn) {
      micNetworkIssueNotifiedRef.current = false;
    }
  }, [micOn]);

  useEffect(() => {
    // In speak mode, keep the mic active continuously. Turn it off when speak mode ends.
    setMicOn(speakModeOn);
  }, [speakModeOn]);

  useEffect(() => {
    if (micOn) {
      startMicRecognition();
      return;
    }
    stopMicRecognition();
    stopLocalMicCapture();
  }, [micOn, startMicRecognition, stopLocalMicCapture, stopMicRecognition]);

  useEffect(() => () => {
    stopMicRecognition();
    stopLocalMicCapture();
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }, [stopLocalMicCapture, stopMicRecognition]);

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
                  <code>{terminal.activeCommand || terminal.lastCommand || "(no command recorded)"}</code>
                </article>
              ))
            )}
          </div>
        </section>
      ) : null}

      <section className={`layout ${speakModeOn ? "layout-speak" : ""}`}>
        <div className="visual-pane">
          <div className="visual-shell">
            <JarvisHUD speakModeOn={speakModeOn} conversationHidden={speakModeOn} />
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
