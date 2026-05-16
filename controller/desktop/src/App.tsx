import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  ServiceId,
  ServiceLogEvent,
  ServiceStatus,
  TerminalSnapshot,
  VoiceprintStatus,
} from "./desktop-api";
import {
  type BotMode,
  type ChatProviderOverride,
  defaultHealthMap,
  extractAssistantText,
  extractFallbackMeta,
  type PendingConfirm,
} from "./appHelpers";
import { downsampleTo16BitPcm, mergeFloat32Chunks, wavBytesFromPcm16 } from "./audioUtils";
import { ConfirmModal } from "./components/ConfirmModal";
import { ConversationPane } from "./components/ConversationPane";
import { ServiceLogsPanel } from "./components/ServiceLogsPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { SpeakModeControls } from "./components/SpeakModeControls";
import { StatusBar } from "./components/StatusBar";
import { TerminalsPanel } from "./components/TerminalsPanel";
import type { ConversationMessage, ConversationRole } from "./types/conversation";
import { sanitizeVoiceCommand, voiceprintEnrollmentPrompt } from "./voiceUtils";
import "./AppClean.css";
import { JarvisHUD } from "./JarvisHUD";

const healthServiceIds: ServiceId[] = ["backend", "executor"];
const coreServiceIds: ServiceId[] = ["backend", "executor"];
const defaultBackendBaseUrl = "http://127.0.0.1:8000";

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
  preRollChunks: Float32Array[];
  preRollSampleCount: number;
  speaking: boolean;
  speechSampleCount: number;
  silenceSampleCount: number;
  cooldownUntilMs: number;
};

type PendingSegment = {
  audio: Float32Array;
  inputSampleRate: number;
};

type VoiceprintEnrollState = {
  active: boolean;
  samplesCollected: number;
  minRequired: number;
  enrollmentPhrases: string[];
};

type AppView = "chat" | "settings";

const MIC_SEGMENT_MIN_SECONDS = 0.35;
const MIC_SEGMENT_MAX_SECONDS = 4.5;
const MIC_PRE_ROLL_SECONDS = 0.35;
const MIC_SILENCE_TAIL_SECONDS = 0.45;
const MIC_TRIGGER_RMS = 0.012;
const MIC_SUSTAIN_RMS = 0.0075;
const MIC_SEND_COOLDOWN_MS = 260;
const MIC_DUPLICATE_WINDOW_MS = 4500;
const PREFER_LOCAL_MIC = true;
export default function App() {
  const [activeView, setActiveView] = useState<AppView>("chat");
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [health, setHealth] = useState(defaultHealthMap);
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);
  const [backendBaseUrl, setBackendBaseUrl] = useState(defaultBackendBaseUrl);
  const [chatInput, setChatInput] = useState("");
  const [inFlightChatCount, setInFlightChatCount] = useState(0);
  const [chatLongRunning, setChatLongRunning] = useState(false);
  const [botMode, setBotMode] = useState<BotMode>("jarvis_cloud");
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [micOn, setMicOn] = useState(false);
  const [speakModeOn, setSpeakModeOn] = useState(false);
  const [assistantSpeaking, setAssistantSpeaking] = useState(false);
  const [localTranscribeBusy, setLocalTranscribeBusy] = useState(false);
  const [voiceDetected, setVoiceDetected] = useState(false);
  const [voiceLockEnabled, setVoiceLockEnabled] = useState(true);
  const [voiceprintStatus, setVoiceprintStatus] = useState<VoiceprintStatus | null>(null);
  const [voiceprintEnrollState, setVoiceprintEnrollState] = useState<VoiceprintEnrollState>({
    active: false,
    samplesCollected: 0,
    minRequired: 5,
    enrollmentPhrases: [],
  });
  const [terminalsOpen, setTerminalsOpen] = useState(false);
  const [terminalsLoading, setTerminalsLoading] = useState(false);
  const [terminals, setTerminals] = useState<TerminalSnapshot[]>([]);
  const [serviceLogsOpen, setServiceLogsOpen] = useState(false);
  const [serviceLogEvents, setServiceLogEvents] = useState<ServiceLogEvent[]>([]);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const micOnRef = useRef(false);
  const micNetworkIssueNotifiedRef = useRef(false);
  const useLocalMicRef = useRef(PREFER_LOCAL_MIC);
  const localMicStateRef = useRef<LocalMicState | null>(null);
  const localMicInitializingRef = useRef(false);
  const localTranscribeBusyRef = useRef(false);
  const pendingLocalSegmentsRef = useRef<PendingSegment[]>([]);
  const voiceWorkerActiveRef = useRef(false);
  const wakeHintShownAtRef = useRef(0);
  const lastTranscriptRef = useRef("");
  const lastTranscriptAtRef = useRef(0);
  const micSuppressUntilRef = useRef(0);
  const perfEnabledRef = useRef(true);
  const ttsAudioContextRef = useRef<AudioContext | null>(null);
  const ttsSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const pollBackoffRef = useRef(0);
  const voiceprintEnrollStateRef = useRef(voiceprintEnrollState);
  const enrollmentPhraseBufferRef = useRef<PendingSegment[]>([]);
  const [enrollmentPhraseReady, setEnrollmentPhraseReady] = useState(false);
  const [enrollmentSubmitBusy, setEnrollmentSubmitBusy] = useState(false);

  const servicesById = useMemo(
    () => services.reduce<Record<string, ServiceStatus>>((acc, service) => {
      acc[service.id] = service;
      return acc;
    }, {}),
    [services]
  );
  
  const areAllCoreRunning = coreServiceIds.every((id) => servicesById[id]?.running);
  const activeProvider = useMemo<ChatProviderOverride>(() => (
    botMode === "local_ollama" ? "ollama" : "huggingface"
  ), [botMode]);
  const activeBotLabel = useMemo(() => {
    if (botMode === "local_ollama") return "Local Bot (Ollama)";
    if (botMode === "huggingface_cloud") return "Cloud Bot (Hugging Face)";
    return "Cloud Bot (Jarvis)";
  }, [botMode]);
  useEffect(() => {
    voiceprintEnrollStateRef.current = voiceprintEnrollState;
  }, [voiceprintEnrollState]);

  const syncEnrollmentPhraseReady = useCallback(() => {
    const chunks = enrollmentPhraseBufferRef.current;
    if (chunks.length === 0) {
      setEnrollmentPhraseReady(false);
      return;
    }
    const totalSamples = chunks.reduce((sum, chunk) => sum + chunk.audio.length, 0);
    const sampleRate = chunks[0]?.inputSampleRate ?? 16000;
    setEnrollmentPhraseReady(totalSamples / sampleRate >= MIC_SEGMENT_MIN_SECONDS);
  }, []);

  const clearEnrollmentPhraseBuffer = useCallback(() => {
    enrollmentPhraseBufferRef.current = [];
    setEnrollmentPhraseReady(false);
  }, []);

  const cycleBotMode = useCallback(() => {
    setBotMode((current) => {
      if (current === "jarvis_cloud") return "huggingface_cloud";
      if (current === "huggingface_cloud") return "local_ollama";
      return "jarvis_cloud";
    });
  }, []);
  const refreshServices = useCallback(async () => {
    const next = await window.desktopApi.listServices();
    setServices(next);
  }, []);

  const refreshBackendBaseUrl = useCallback(async () => {
    const nextBaseUrl = await window.desktopApi.getServiceBaseUrl("backend");
    setBackendBaseUrl(nextBaseUrl || defaultBackendBaseUrl);
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
    await Promise.all([refreshServices(), refreshHealth(), refreshBackendBaseUrl()]);
  }, [refreshBackendBaseUrl, refreshHealth, refreshServices]);

  const refreshVoiceprintStatus = useCallback(async () => {
    const response = await window.desktopApi.getVoiceprintStatus(backendBaseUrl);
    if ("error" in response) return;
    setVoiceprintStatus(response.data);
    const d = response.data;
    const partial =
      !d.enabled && d.samples_collected > 0 && d.samples_collected < d.min_required_samples;
    setVoiceprintEnrollState((prev) => {
      if (partial) {
        return {
          active: true,
          samplesCollected: d.samples_collected,
          minRequired: d.min_required_samples,
          enrollmentPhrases: d.enrollment_phrases?.length ? d.enrollment_phrases : prev.enrollmentPhrases,
        };
      }
      return {
        ...prev,
        minRequired: d.min_required_samples,
        enrollmentPhrases: d.enrollment_phrases?.length ? d.enrollment_phrases : prev.enrollmentPhrases,
      };
    });
  }, [backendBaseUrl]);

  const addMessage = useCallback((role: ConversationRole, text: string) => {
    const payload = text.trim();
    if (!payload) return;
    setMessages((previous) => [
      ...previous,
      {
        id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        role,
        text: payload,
        createdAt: Date.now(),
      },
    ]);
  }, []);

  const logPerf = useCallback((label: string, metrics: Record<string, number | string | boolean>) => {
    if (!perfEnabledRef.current) return;
    const payload = Object.entries(metrics).map(([key, value]) => `${key}=${value}`).join(" ");
    console.debug(`[perf] ${label} ${payload}`);
  }, []);

  const voiceStatus = useMemo(() => {
    if (assistantSpeaking) return "speaking";
    if (inFlightChatCount > 0 || localTranscribeBusy) return "processing";
    if (micOn) return "listening";
    return "idle";
  }, [assistantSpeaking, inFlightChatCount, localTranscribeBusy, micOn]);

  const voiceStatusLabel = useMemo(() => {
    if (voiceStatus === "speaking") return "Speaking...";
    if (voiceStatus === "processing") {
      return chatLongRunning ? "Still processing..." : "Processing...";
    }
    if (voiceStatus === "listening") return voiceDetected ? "Listening (voice detected)" : "Listening...";
    return "Not listening";
  }, [chatLongRunning, voiceDetected, voiceStatus]);

  const backendHealthPayload = useMemo(() => {
    const payload = health.backend.data;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      return null;
    }
    return payload as { stt_ready?: boolean; tts_ready?: boolean };
  }, [health.backend.data]);

  const jarvisFullyReady = useMemo(
    () =>
      health.backend.ok &&
      health.executor.ok &&
      backendHealthPayload?.stt_ready === true &&
      backendHealthPayload?.tts_ready === true,
    [backendHealthPayload, health.backend.ok, health.executor.ok],
  );

  const backendBadge = useMemo(() => {
    if (!health.backend.ok) {
      return { className: "error" as const, label: "Offline" };
    }
    if (backendHealthPayload?.stt_ready === true && backendHealthPayload?.tts_ready === true) {
      return { className: "ok" as const, label: "Online" };
    }
    return { className: "warn" as const, label: "Warming up…" };
  }, [backendHealthPayload, health.backend.ok]);

  useEffect(() => {
    return window.desktopApi.onServiceLog((payload) => {
      setServiceLogEvents((prev) => [...prev.slice(-240), payload]);
    });
  }, []);

  useEffect(() => {
    let timeoutId = 0;
    let cancelled = false;

    const runTick = async () => {
      if (cancelled) return;
      await refreshAll();
      if (cancelled) return;
      const voiceEveryOther = pollBackoffRef.current % 2 === 0;
      pollBackoffRef.current += 1;
      if (voiceEveryOther) {
        void refreshVoiceprintStatus();
      }
      const baseMs = jarvisFullyReady ? 5000 : 2500;
      timeoutId = window.setTimeout(() => {
        void runTick();
      }, baseMs);
    };

    void runTick();
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [jarvisFullyReady, refreshAll, refreshVoiceprintStatus]);

  const runServiceAction = async (action: () => Promise<unknown>) => {
    await action();
    await refreshAll();
  };

  const handleStartOrRedoVoiceprint = useCallback(async () => {
    const resetResponse = await window.desktopApi.resetVoiceprint(backendBaseUrl);
    if ("error" in resetResponse) {
      addMessage("system", `Voiceprint reset error: ${resetResponse.error}`);
      return;
    }
    const minRequired = resetResponse.data.min_required_samples;
    const enrollmentPhrases = resetResponse.data.enrollment_phrases ?? [];
    const first = enrollmentPhrases[0] ?? "";
    setVoiceprintStatus(resetResponse.data);
    clearEnrollmentPhraseBuffer();
    setVoiceprintEnrollState({ active: true, samplesCollected: 0, minRequired, enrollmentPhrases });
    setMicOn(true);
    addMessage(
      "system",
      `Voiceprint enrollment started (${minRequired} phrases). Say phrase 1 at your own pace, then use Submit phrase in Settings when finished—not after each pause. First phrase: "${first}"`,
    );
  }, [addMessage, backendBaseUrl, clearEnrollmentPhraseBuffer]);

  const submitEnrollmentPhrase = useCallback(async () => {
    if (enrollmentSubmitBusy || !voiceprintEnrollStateRef.current.active) return;
    const chunks = enrollmentPhraseBufferRef.current;
    if (chunks.length === 0) return;

    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.audio.length, 0);
    const sampleRate = chunks[0].inputSampleRate;
    if (totalLength / sampleRate < MIC_SEGMENT_MIN_SECONDS) return;

    setEnrollmentSubmitBusy(true);
    try {
      const merged = mergeFloat32Chunks(
        chunks.map((chunk) => chunk.audio),
        totalLength,
      );
      const pcm = downsampleTo16BitPcm(merged, sampleRate, 16000);
      if (pcm.length < 8000) {
        addMessage("system", "Recording too short. Speak a bit longer, then submit again.");
        return;
      }
      const wavBytes = wavBytesFromPcm16(pcm, 16000);
      const enrollResponse = await window.desktopApi.enrollVoiceprintSample(wavBytes, backendBaseUrl);
      if ("error" in enrollResponse) {
        addMessage("system", `Voiceprint enroll error: ${enrollResponse.error}`);
        return;
      }
      clearEnrollmentPhraseBuffer();
      const {
        samples_collected,
        min_required_samples,
        ready_to_finalize,
        enrollment_phrases,
        next_enrollment_phrase,
      } = enrollResponse.data;
      setVoiceprintEnrollState((prev) => ({
        active: !ready_to_finalize,
        samplesCollected: samples_collected,
        minRequired: min_required_samples,
        enrollmentPhrases: enrollment_phrases?.length ? enrollment_phrases : prev.enrollmentPhrases,
      }));
      if (ready_to_finalize) {
        const finalizeResponse = await window.desktopApi.finalizeVoiceprint(backendBaseUrl);
        if ("error" in finalizeResponse) {
          addMessage("system", `Voiceprint finalize error: ${finalizeResponse.error}`);
        } else {
          setVoiceprintStatus(finalizeResponse.data);
          addMessage("system", "Voiceprint setup complete. Speaker verification is now enabled.");
        }
      } else {
        const nextHint = next_enrollment_phrase ? ` Next phrase: "${next_enrollment_phrase}"` : "";
        addMessage("system", `Phrase ${samples_collected}/${min_required_samples} saved.${nextHint}`);
      }
    } finally {
      setEnrollmentSubmitBusy(false);
    }
  }, [addMessage, backendBaseUrl, clearEnrollmentPhraseBuffer]);

  const suppressMicFor = useCallback((ms: number) => {
    const until = Date.now() + Math.max(0, ms);
    micSuppressUntilRef.current = Math.max(micSuppressUntilRef.current, until);
  }, []);

  const isMicSuppressed = useCallback(() => Date.now() < micSuppressUntilRef.current, []);

  const speakAssistant = useCallback(
    async (text: string) => {
      const cleanText = text.trim();
      if (!cleanText) return;
      const wordCount = cleanText.split(/\s+/).filter(Boolean).length;
      const fallbackMs = Math.min(18000, Math.max(1200, wordCount * 340 + 900));
      suppressMicFor(fallbackMs);
      try {
        const result = await window.desktopApi.synthesizeSpeech(cleanText, backendBaseUrl);
        if ("error" in result) {
          addMessage("system", `TTS unavailable: ${result.error}`);
          setAssistantSpeaking(false);
          return;
        }
        const b64 = result.data.audio_base64;
        if (!b64) {
          addMessage("system", "TTS returned no audio.");
          setAssistantSpeaking(false);
          return;
        }
        const binary = atob(b64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) {
          bytes[i] = binary.charCodeAt(i);
        }
        const copy = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        let ctx = ttsAudioContextRef.current;
        if (!ctx || ctx.state === "closed") {
          ctx = new AudioContext();
          ttsAudioContextRef.current = ctx;
        }
        if (ttsSourceRef.current) {
          try {
            ttsSourceRef.current.stop();
          } catch {
            /* ended */
          }
          ttsSourceRef.current = null;
        }
        const buffer = await ctx.decodeAudioData(copy);
        const durationMs = Math.ceil(buffer.duration * 1000);
        suppressMicFor(durationMs + 1400);
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(ctx.destination);
        source.onended = () => {
          setAssistantSpeaking(false);
          suppressMicFor(850);
          ttsSourceRef.current = null;
        };
        setAssistantSpeaking(false);
        await ctx.resume();
        setAssistantSpeaking(true);
        suppressMicFor(1200);
        source.start(0);
        ttsSourceRef.current = source;
      } catch (e) {
        const msg = e instanceof Error ? e.message : "playback failed";
        addMessage("system", `TTS playback error: ${msg}`);
        setAssistantSpeaking(false);
      }
    },
    [addMessage, backendBaseUrl, suppressMicFor],
  );

  const sendText = useCallback(async function sendTextImpl(
    raw: string,
    chatProvider?: ChatProviderOverride,
    suppressUserMessage = false,
  ) {
    const text = raw.trim();
    if (!text) return;
    const requestStart = performance.now();
    if (!suppressUserMessage) {
      addMessage("user", text);
    }
    setInFlightChatCount((current) => current + 1);
    let longRunningTimer: number | null = window.setTimeout(() => {
      setChatLongRunning(true);
    }, 1200);
    const provider = chatProvider ?? activeProvider;
    try {
      const result = await window.desktopApi.interactWithBackend(text, backendBaseUrl, provider);
      if ("error" in result) {
        addMessage("system", `Backend error: ${result.error}`);
        return;
      }
      const reply = extractAssistantText(result.data);
      const fallbackMeta = extractFallbackMeta(result.data);
      addMessage("assistant", reply);
      if (fallbackMeta && provider !== "ollama") {
        const providerName = fallbackMeta.chatbot_provider ?? "huggingface";
        setPendingConfirm({
          title: "Cloud provider unavailable",
          message: `${providerName} is currently unavailable. Run this request locally with Ollama, or wait and retry the cloud provider later.`,
          confirmLabel: "Use Ollama",
          cancelLabel: "Wait",
          onConfirm: () => {
            setPendingConfirm(null);
            addMessage("system", "Switching this request to local Ollama.");
            void sendTextImpl(text, "ollama", true);
          },
          onCancel: () => {
            setPendingConfirm(null);
            addMessage("system", "Keeping cloud mode. Retry once it is available.");
          },
        });
        return;
      }
      if (speakModeOn) {
        void speakAssistant(reply);
      }
      logPerf("chat.interact", {
        provider,
        totalMs: (performance.now() - requestStart).toFixed(1),
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unknown request error";
      addMessage("system", message);
    } finally {
      if (longRunningTimer !== null) {
        window.clearTimeout(longRunningTimer);
        longRunningTimer = null;
      }
      setInFlightChatCount((current) => {
        const next = Math.max(0, current - 1);
        if (next === 0) {
          setChatLongRunning(false);
        }
        return next;
      });
      await refreshHealth();
    }
  }, [activeProvider, addMessage, backendBaseUrl, logPerf, refreshHealth, speakAssistant, speakModeOn]);

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

  const processVoiceQueue = useCallback(async () => {
    if (voiceWorkerActiveRef.current) return;
    voiceWorkerActiveRef.current = true;
    localTranscribeBusyRef.current = true;
    setLocalTranscribeBusy(true);
    try {
      while (pendingLocalSegmentsRef.current.length > 0 && micOnRef.current) {
        const nextSegment = pendingLocalSegmentsRef.current.shift();
        if (!nextSegment || isMicSuppressed()) {
          continue;
        }
        const pcm = downsampleTo16BitPcm(nextSegment.audio, nextSegment.inputSampleRate, 16000);
        if (pcm.length < 8000) {
          continue;
        }
        const encodeStart = performance.now();
        const wavBytes = wavBytesFromPcm16(pcm, 16000);
        const encodedMs = performance.now() - encodeStart;
        if (voiceprintStatus?.enabled) {
          const verifyResponse = await window.desktopApi.verifyVoiceprint(wavBytes, backendBaseUrl);
          if ("error" in verifyResponse) {
            addMessage("system", `Voice verification error: ${verifyResponse.error}`);
            continue;
          }
          if (!verifyResponse.data.matched) {
            logPerf("mic.voiceprint_reject", {
              score: verifyResponse.data.score,
              threshold: verifyResponse.data.threshold,
            });
            continue;
          }
        }
        const transcribeStart = performance.now();
        const response = await window.desktopApi.transcribeAudio(wavBytes, backendBaseUrl);
        const transcribeMs = performance.now() - transcribeStart;
        if ("error" in response) {
          addMessage("system", `Transcription error: ${response.error}`);
          continue;
        }
        const transcript = (response.data.text ?? "").trim();
        if (!transcript || isMicSuppressed()) {
          continue;
        }
        const commandText = sanitizeVoiceCommand(transcript, voiceLockEnabled);
        if (!commandText) {
          const now = Date.now();
          if (voiceLockEnabled && now - wakeHintShownAtRef.current > 7000) {
            wakeHintShownAtRef.current = now;
            addMessage("system", "Voice lock is on. Start commands with 'Jarvis ...'.");
          }
          continue;
        }
        const now = Date.now();
        const normalized = commandText.toLowerCase();
        if (lastTranscriptRef.current === normalized && now - lastTranscriptAtRef.current < MIC_DUPLICATE_WINDOW_MS) {
          continue;
        }
        lastTranscriptRef.current = normalized;
        lastTranscriptAtRef.current = now;
        logPerf("mic.local_segment", {
          pcmSamples: pcm.length,
          wavBytes: wavBytes.length,
          encodedMs: encodedMs.toFixed(1),
          transcribeMs: transcribeMs.toFixed(1),
          queueDepth: pendingLocalSegmentsRef.current.length,
          voiceLockEnabled,
        });
        void sendText(commandText);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown transcription failure";
      addMessage("system", `Transcription error: ${message}`);
    } finally {
      localTranscribeBusyRef.current = false;
      setLocalTranscribeBusy(false);
      voiceWorkerActiveRef.current = false;
    }
  }, [addMessage, backendBaseUrl, isMicSuppressed, logPerf, sendText, voiceLockEnabled, voiceprintStatus?.enabled]);

  const enqueueLocalSegment = useCallback((audio: Float32Array, inputSampleRate: number) => {
    if (!micOnRef.current || isMicSuppressed()) return;
    if (voiceprintEnrollStateRef.current.active) {
      enrollmentPhraseBufferRef.current.push({ audio, inputSampleRate });
      syncEnrollmentPhraseReady();
      return;
    }
    pendingLocalSegmentsRef.current.push({ audio, inputSampleRate });
    void processVoiceQueue();
  }, [isMicSuppressed, processVoiceQueue, syncEnrollmentPhraseReady]);

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
        preRollChunks: [],
        preRollSampleCount: 0,
        speaking: false,
        speechSampleCount: 0,
        silenceSampleCount: 0,
        cooldownUntilMs: 0,
      };

      processor.onaudioprocess = (event) => {
        if (!micOnRef.current) return;
        if (isMicSuppressed()) {
          setVoiceDetected(false);
          state.chunks = [];
          state.sampleCount = 0;
          state.preRollChunks = [];
          state.preRollSampleCount = 0;
          state.speaking = false;
          state.speechSampleCount = 0;
          state.silenceSampleCount = 0;
          state.cooldownUntilMs = Math.max(state.cooldownUntilMs, Date.now() + MIC_SEND_COOLDOWN_MS);
          return;
        }
        const chunk = new Float32Array(event.inputBuffer.getChannelData(0));
        let energy = 0;
        for (let i = 0; i < chunk.length; i += 1) {
          energy += chunk[i] * chunk[i];
        }
        const rms = Math.sqrt(energy / chunk.length);

        const nowMs = Date.now();
        const preRollMaxSamples = Math.floor(state.context.sampleRate * MIC_PRE_ROLL_SECONDS);
        state.preRollChunks.push(chunk);
        state.preRollSampleCount += chunk.length;
        while (state.preRollSampleCount > preRollMaxSamples && state.preRollChunks.length > 1) {
          const removed = state.preRollChunks.shift();
          if (!removed) break;
          state.preRollSampleCount -= removed.length;
        }

        const isVoice = rms >= MIC_TRIGGER_RMS || (state.speaking && rms >= MIC_SUSTAIN_RMS);
        setVoiceDetected((prev) => (prev === isVoice ? prev : isVoice));
        if (!state.speaking) {
          if (!isVoice || nowMs < state.cooldownUntilMs) {
            return;
          }
          state.speaking = true;
          state.chunks = [...state.preRollChunks];
          state.sampleCount = state.preRollSampleCount;
          state.speechSampleCount = chunk.length;
          state.silenceSampleCount = 0;
        } else {
          state.chunks.push(chunk);
          state.sampleCount += chunk.length;
          if (isVoice) {
            state.speechSampleCount += chunk.length;
            state.silenceSampleCount = 0;
          } else {
            state.silenceSampleCount += chunk.length;
          }
        }

        const segmentSeconds = state.sampleCount / state.context.sampleRate;
        const speechSeconds = state.speechSampleCount / state.context.sampleRate;
        const silenceSeconds = state.silenceSampleCount / state.context.sampleRate;
        const shouldEmit = segmentSeconds >= MIC_SEGMENT_MAX_SECONDS
          || (speechSeconds >= MIC_SEGMENT_MIN_SECONDS && silenceSeconds >= MIC_SILENCE_TAIL_SECONDS);
        if (shouldEmit) {
          const merged = mergeFloat32Chunks(state.chunks, state.sampleCount);
          state.chunks = [];
          state.sampleCount = 0;
          state.preRollChunks = [];
          state.preRollSampleCount = 0;
          state.speaking = false;
          setVoiceDetected(false);
          state.speechSampleCount = 0;
          state.silenceSampleCount = 0;
          state.cooldownUntilMs = nowMs + MIC_SEND_COOLDOWN_MS;
          if (speechSeconds >= MIC_SEGMENT_MIN_SECONDS) {
            enqueueLocalSegment(merged, state.context.sampleRate);
          }
        }
      };

      source.connect(processor);
      processor.connect(sink);
      sink.connect(context.destination);
      localMicStateRef.current = state;
      localMicInitializingRef.current = false;
      if (!micNetworkIssueNotifiedRef.current && !PREFER_LOCAL_MIC) {
        addMessage("system", "Mic switched to local transcription mode.");
        micNetworkIssueNotifiedRef.current = true;
      }
    } catch (error) {
      localMicInitializingRef.current = false;
      const message = error instanceof Error ? error.message : "Unable to access microphone";
      addMessage("system", `Mic access error: ${message}`);
      setMicOn(false);
    }
  }, [addMessage, enqueueLocalSegment, isMicSuppressed]);

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
          if (transcript && !isMicSuppressed()) {
            const commandText = sanitizeVoiceCommand(transcript, voiceLockEnabled);
            if (commandText) {
              void sendText(commandText);
            }
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
  }, [addMessage, isMicSuppressed, sendText, startLocalMicCapture, voiceLockEnabled]);

  useEffect(() => {
    micOnRef.current = micOn;
    if (!micOn) {
      micNetworkIssueNotifiedRef.current = false;
      setVoiceDetected(false);
      pendingLocalSegmentsRef.current = [];
      voiceWorkerActiveRef.current = false;
      localTranscribeBusyRef.current = false;
      setLocalTranscribeBusy(false);
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
    if (ttsSourceRef.current) {
      try {
        ttsSourceRef.current.stop();
      } catch {
        /* ended */
      }
      ttsSourceRef.current = null;
    }
    void ttsAudioContextRef.current?.close();
    ttsAudioContextRef.current = null;
    setAssistantSpeaking(false);
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
    if (!health.backend.ok) return;
    const text = chatInput.trim();
    if (!text) return;
    setChatInput("");
    await sendText(text);
  };

  const settingsOpen = activeView === "settings";
  const voiceprintSummary = voiceprintEnrollState.active
    ? `enrolling ${voiceprintEnrollState.samplesCollected}/${voiceprintEnrollState.minRequired}`
    : voiceprintStatus?.enabled
      ? "enabled"
      : "not set";

  const toggleSettings = () => {
    if (settingsOpen) {
      setActiveView("chat");
      return;
    }
    setActiveView("settings");
    setTerminalsOpen(false);
    setServiceLogsOpen(false);
  };

  const toggleTerminals = () => {
    const next = !terminalsOpen;
    setTerminalsOpen(next);
    if (next) {
      void loadTerminals();
      setActiveView("chat");
      setServiceLogsOpen(false);
    }
  };

  const toggleServiceLogs = () => {
    const next = !serviceLogsOpen;
    setServiceLogsOpen(next);
    if (next) {
      setTerminalsOpen(false);
      setActiveView("chat");
    }
  };

  const exitSpeakMode = () => {
    setSpeakModeOn(false);
    window.speechSynthesis.cancel();
    setAssistantSpeaking(false);
    setVoiceDetected(false);
  };

  return (
    <main className={`app ${speakModeOn ? "speak-mode" : ""} ${serviceLogsOpen ? "service-logs-open" : ""}`}>
      <StatusBar
        settingsOpen={settingsOpen}
        areAllCoreRunning={areAllCoreRunning}
        activeBotLabel={activeBotLabel}
        backendBadge={backendBadge}
        executorOnline={health.executor.ok}
        onToggleSettings={toggleSettings}
        onStartStopJarvis={() =>
          void runServiceAction(async () => {
            if (areAllCoreRunning) {
              await window.desktopApi.stopAllServices();
              return;
            }
            const started = await window.desktopApi.startAllServices();
            for (const err of started.errors) {
              addMessage("system", err);
            }
          })
        }
        onToggleTerminals={toggleTerminals}
        onToggleServiceLogs={toggleServiceLogs}
        onCycleBotMode={cycleBotMode}
      />

      {terminalsOpen ? (
        <TerminalsPanel
          terminals={terminals}
          loading={terminalsLoading}
          onRefresh={() => void loadTerminals()}
          onClose={() => setTerminalsOpen(false)}
        />
      ) : null}

      {serviceLogsOpen ? (
        <ServiceLogsPanel
          events={serviceLogEvents}
          onClear={() => setServiceLogEvents([])}
          onClose={() => setServiceLogsOpen(false)}
        />
      ) : null}

      {settingsOpen ? (
        <SettingsPanel
          voiceprintStatus={voiceprintStatus}
          voiceprintEnrollState={voiceprintEnrollState}
          enrollmentPrompt={voiceprintEnrollmentPrompt(voiceprintEnrollState)}
          enrollmentPhraseReady={enrollmentPhraseReady}
          enrollmentSubmitBusy={enrollmentSubmitBusy}
          voiceDetected={voiceDetected}
          onStartOrRedoVoiceprint={() => void handleStartOrRedoVoiceprint()}
          onSubmitEnrollmentPhrase={() => void submitEnrollmentPhrase()}
          onRefresh={() => void refreshAll()}
          onOpenDevTools={() => void window.desktopApi.openDevTools()}
          onClose={() => setActiveView("chat")}
        />
      ) : null}

      <ConfirmModal
        open={pendingConfirm !== null}
        title={pendingConfirm?.title ?? ""}
        message={pendingConfirm?.message ?? ""}
        confirmLabel={pendingConfirm?.confirmLabel}
        cancelLabel={pendingConfirm?.cancelLabel}
        onConfirm={() => pendingConfirm?.onConfirm()}
        onCancel={() => pendingConfirm?.onCancel()}
      />

      <section className={`layout ${speakModeOn ? "layout-speak" : ""}`}>
        <div className="visual-pane">
          <div className="visual-shell">
            <JarvisHUD
              speakModeOn={speakModeOn}
              conversationHidden={speakModeOn}
              isSpeaking={assistantSpeaking}
            />
          </div>
        </div>

        <ConversationPane
          hidden={speakModeOn}
          activeBotLabel={activeBotLabel}
          voiceprintSummary={voiceprintSummary}
          backendOnline={health.backend.ok}
          messages={messages}
          chatInput={chatInput}
          inFlightChat={inFlightChatCount > 0}
          micOn={micOn}
          voiceLockEnabled={voiceLockEnabled}
          speakModeOn={speakModeOn}
          voiceDetected={voiceDetected}
          onInputChange={setChatInput}
          onSubmit={handleSend}
          onToggleMic={() => setMicOn((value) => !value)}
          onToggleVoiceLock={() => setVoiceLockEnabled((value) => !value)}
          onToggleSpeakMode={() => {
            setSpeakModeOn((value) => !value);
            if (speakModeOn) {
              window.speechSynthesis.cancel();
              setAssistantSpeaking(false);
            }
          }}
        />
      </section>

      {speakModeOn ? (
        <SpeakModeControls
          voiceStatus={voiceStatus}
          voiceStatusLabel={voiceStatusLabel}
          micOn={micOn}
          backendOnline={health.backend.ok}
          onToggleMic={() => setMicOn((value) => !value)}
          onExitSpeakMode={exitSpeakMode}
        />
      ) : null}

    </main>
  );
}
