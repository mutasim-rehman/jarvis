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
import { downsampleTo16BitPcm, mergeFloat32Chunks, prepareVoiceprintAudio, wavBytesFromPcm16 } from "./audioUtils";
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
import { useAuth } from "./auth/AuthProvider";

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
  canFinalize: boolean;
};

type TtsStreamEvent =
  | {
      type: "audio_chunk";
      audio_base64?: string;
    }
  | {
      type: "done";
    };

type AppView = "chat" | "settings";

const MIC_SEGMENT_MIN_SECONDS = 0.35;
const MIC_SEGMENT_MAX_SECONDS = 4.5;
const MIC_PRE_ROLL_SECONDS = 0.35;
const MIC_SILENCE_TAIL_SECONDS = 0.35;
const MIC_TRIGGER_RMS = 0.012;
const MIC_SUSTAIN_RMS = 0.0075;
const MIC_SEND_COOLDOWN_MS = 260;
const MIC_DUPLICATE_WINDOW_MS = 4500;
// One pass keeps latency low; two passes need a second mic segment before STT runs.
const SPEAK_MODE_VOICEPRINT_REQUIRED_PASSES = 1;
const PREFER_LOCAL_MIC = true;
export default function App() {
  const { accessToken } = useAuth();
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
  const [lastHeardText, setLastHeardText] = useState("");
  const [localTranscribeBusy, setLocalTranscribeBusy] = useState(false);
  const [voiceDetected, setVoiceDetected] = useState(false);
  const [voiceLockEnabled, setVoiceLockEnabled] = useState(true);
  const [voiceprintStatus, setVoiceprintStatus] = useState<VoiceprintStatus | null>(null);
  const [voiceprintEnrollState, setVoiceprintEnrollState] = useState<VoiceprintEnrollState>({
    active: false,
    samplesCollected: 0,
    minRequired: 5,
    enrollmentPhrases: [],
    canFinalize: false,
  });
  const [voiceprintEnabled, setVoiceprintEnabled] = useState<boolean>(
    () => localStorage.getItem("voiceprint_enabled") !== "false",
  );
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
  const deferredWhileSpeakingRef = useRef<PendingSegment[]>([]);
  const flushDeferredSegmentsRef = useRef<() => void>(() => {});
  const voiceWorkerActiveRef = useRef(false);
  const wakeHintShownAtRef = useRef(0);
  const lastTranscriptRef = useRef("");
  const lastTranscriptAtRef = useRef(0);
  const voiceprintConsecutivePassesRef = useRef(0);
  const micSuppressUntilRef = useRef(0);
  const perfEnabledRef = useRef(true);
  const ttsAudioContextRef = useRef<AudioContext | null>(null);
  const ttsSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const ttsScheduledSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const ttsAbortControllerRef = useRef<AbortController | null>(null);
  const ttsGenerationRef = useRef(0);
  const assistantSpeakingRef = useRef(false);
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
  const activeProvider = useMemo<ChatProviderOverride | undefined>(() => (
    botMode === "local_ollama" ? "ollama" : undefined
  ), [botMode]);
  const activeBotLabel = useMemo(() => {
    if (botMode === "local_ollama") return "Local Bot (Ollama)";
    if (botMode === "huggingface_cloud") return "Cloud Bot (Hugging Face)";
    return "Cloud Bot (Jarvis)";
  }, [botMode]);
  useEffect(() => {
    voiceprintEnrollStateRef.current = voiceprintEnrollState;
  }, [voiceprintEnrollState]);

  useEffect(() => {
    localStorage.setItem("voiceprint_enabled", voiceprintEnabled ? "true" : "false");
  }, [voiceprintEnabled]);

  useEffect(() => {
    assistantSpeakingRef.current = assistantSpeaking;
  }, [assistantSpeaking]);

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
    const targetSamples = d.target_samples ?? d.enrollment_phrases?.length ?? d.min_required_samples;
    const partial =
      !d.enabled && d.samples_collected > 0 && d.samples_collected < targetSamples;
    setVoiceprintEnrollState((prev) => {
      if (partial) {
        return {
          active: true,
          samplesCollected: d.samples_collected,
          minRequired: d.min_required_samples,
          enrollmentPhrases: d.enrollment_phrases?.length ? d.enrollment_phrases : prev.enrollmentPhrases,
          canFinalize: d.samples_collected >= d.min_required_samples,
        };
      }
      return {
        ...prev,
        minRequired: d.min_required_samples,
        enrollmentPhrases: d.enrollment_phrases?.length ? d.enrollment_phrases : prev.enrollmentPhrases,
        canFinalize: false,
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
    setVoiceprintEnrollState({ active: true, samplesCollected: 0, minRequired, enrollmentPhrases, canFinalize: false });
    setMicOn(true);
    addMessage(
      "system",
      `Voiceprint enrollment started (${minRequired} required phrases plus optional room calibration). Say phrase 1 at your own pace, then use Submit phrase in Settings when finished. First phrase: "${first}"`,
    );
  }, [addMessage, backendBaseUrl, clearEnrollmentPhraseBuffer]);

  const finalizeVoiceprintEnrollment = useCallback(async () => {
    const finalizeResponse = await window.desktopApi.finalizeVoiceprint(backendBaseUrl);
    if ("error" in finalizeResponse) {
      addMessage("system", `Voiceprint finalize error: ${finalizeResponse.error}`);
      return;
    }
    setVoiceprintStatus(finalizeResponse.data);
    setVoiceprintEnrollState((prev) => ({
      ...prev,
      active: false,
      samplesCollected: finalizeResponse.data.samples_collected,
      minRequired: finalizeResponse.data.min_required_samples,
      canFinalize: false,
    }));
    voiceprintConsecutivePassesRef.current = 0;
    addMessage("system", "Voiceprint setup complete. Speaker verification is now enabled for mic and speak mode.");
  }, [addMessage, backendBaseUrl]);

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
      const wavBytes = prepareVoiceprintAudio(merged, sampleRate);
      if (wavBytes.length < 16044) {
        addMessage("system", "Recording too short. Speak a bit longer, then submit again.");
        return;
      }
      const enrollResponse = await window.desktopApi.enrollVoiceprintSample(wavBytes, backendBaseUrl);
      if ("error" in enrollResponse) {
        addMessage("system", `Voiceprint enroll error: ${enrollResponse.error}`);
        return;
      }
      clearEnrollmentPhraseBuffer();
      const {
        samples_collected,
        min_required_samples,
        target_samples,
        ready_to_finalize,
        enrollment_phrases,
        next_enrollment_phrase,
      } = enrollResponse.data;
      const targetSamples = target_samples ?? enrollment_phrases?.length ?? min_required_samples;
      const enrollmentComplete = samples_collected >= targetSamples;
      setVoiceprintEnrollState((prev) => ({
        active: !enrollmentComplete,
        samplesCollected: samples_collected,
        minRequired: min_required_samples,
        enrollmentPhrases: enrollment_phrases?.length ? enrollment_phrases : prev.enrollmentPhrases,
        canFinalize: ready_to_finalize && !enrollmentComplete,
      }));
      if (enrollmentComplete) {
        await finalizeVoiceprintEnrollment();
      } else {
        const nextHint = next_enrollment_phrase ? ` Next phrase: "${next_enrollment_phrase}"` : "";
        const finalizeHint = ready_to_finalize ? " You can finish now, or add the optional room calibration sample." : "";
        addMessage("system", `Phrase ${samples_collected}/${targetSamples} saved.${nextHint}${finalizeHint}`);
      }
    } finally {
      setEnrollmentSubmitBusy(false);
    }
  }, [addMessage, backendBaseUrl, clearEnrollmentPhraseBuffer, finalizeVoiceprintEnrollment]);

  const suppressMicFor = useCallback((ms: number) => {
    const until = Date.now() + Math.max(0, ms);
    micSuppressUntilRef.current = Math.max(micSuppressUntilRef.current, until);
  }, []);

  const isMicSuppressed = useCallback(() => Date.now() < micSuppressUntilRef.current, []);

  const stopCurrentTts = useCallback(() => {
    ttsGenerationRef.current += 1;
    ttsAbortControllerRef.current?.abort();
    ttsAbortControllerRef.current = null;
    for (const source of ttsScheduledSourcesRef.current) {
      try {
        source.stop();
      } catch {
        /* already ended */
      }
      try {
        source.disconnect();
      } catch {
        /* already disconnected */
      }
    }
    ttsScheduledSourcesRef.current = [];
    ttsSourceRef.current = null;
    deferredWhileSpeakingRef.current = [];
    micSuppressUntilRef.current = Date.now() + 120;
    assistantSpeakingRef.current = false;
    setAssistantSpeaking(false);
  }, []);

  const speakAssistant = useCallback(
    async (text: string) => {
      const cleanText = text.trim();
      if (!cleanText) return;
      deferredWhileSpeakingRef.current = [];
      const wordCount = cleanText.split(/\s+/).filter(Boolean).length;
      const fallbackMs = Math.min(18000, Math.max(1200, wordCount * 340 + 900));
      stopCurrentTts();
      const generation = ttsGenerationRef.current;
      const streamController = new AbortController();
      ttsAbortControllerRef.current = streamController;
      setLastHeardText("");
      suppressMicFor(fallbackMs);

      const base64ToArrayBuffer = (b64: string) => {
        const binary = atob(b64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) {
          bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
      };

      let ctx = ttsAudioContextRef.current;
      if (!ctx || ctx.state === "closed") {
        ctx = new AudioContext();
        ttsAudioContextRef.current = ctx;
      }

      const playFullTtsFallback = async () => {
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
        if (ttsGenerationRef.current !== generation) return;
        const buffer = await ctx.decodeAudioData(base64ToArrayBuffer(b64));
        if (ttsGenerationRef.current !== generation) return;
        const durationMs = Math.ceil(buffer.duration * 1000);
        suppressMicFor(durationMs + 2500);
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(ctx.destination);
        ttsSourceRef.current = source;
        ttsScheduledSourcesRef.current = [source];
        source.onended = () => {
          try {
            source.disconnect();
          } catch {
            /* already disconnected */
          }
          ttsScheduledSourcesRef.current = ttsScheduledSourcesRef.current.filter((item) => item !== source);
          if (ttsGenerationRef.current !== generation) return;
          assistantSpeakingRef.current = false;
          setAssistantSpeaking(false);
          suppressMicFor(1500);
          if (ttsSourceRef.current === source) {
            ttsSourceRef.current = null;
          }
          flushDeferredSegmentsRef.current();
        };
        await ctx.resume();
        if (ttsGenerationRef.current !== generation) return;
        assistantSpeakingRef.current = true;
        setAssistantSpeaking(true);
        suppressMicFor(1500);
        source.start(0);
      };

      try {
        const response = await fetch(`${backendBaseUrl.replace(/\/+$/, "")}/api/tts/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: cleanText }),
          signal: streamController.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Streaming TTS failed ${response.status}: ${response.statusText || "unavailable"}`);
        }

        await ctx.resume();
        if (ttsGenerationRef.current !== generation) return;
        assistantSpeakingRef.current = true;
        setAssistantSpeaking(true);
        suppressMicFor(1500);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let bufferText = "";
        let scheduledTime = ctx.currentTime + 0.08;
        let scheduledCount = 0;
        let endedCount = 0;
        let streamDone = false;

        const finishIfComplete = () => {
          if (!streamDone || endedCount < scheduledCount || ttsGenerationRef.current !== generation) return;
          assistantSpeakingRef.current = false;
          setAssistantSpeaking(false);
          suppressMicFor(850);
          ttsSourceRef.current = null;
          flushDeferredSegmentsRef.current();
        };

        const scheduleChunk = async (audioBase64: string) => {
          if (!audioBase64 || ttsGenerationRef.current !== generation) return;
          const audioBuffer = await ctx.decodeAudioData(base64ToArrayBuffer(audioBase64));
          if (ttsGenerationRef.current !== generation) return;
          const source = ctx.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(ctx.destination);
          const startAt = Math.max(scheduledTime, ctx.currentTime + 0.02);
          scheduledTime = startAt + audioBuffer.duration;
          scheduledCount += 1;
          ttsSourceRef.current = source;
          ttsScheduledSourcesRef.current.push(source);
          suppressMicFor(Math.ceil((scheduledTime - ctx.currentTime) * 1000) + 900);
          source.onended = () => {
            try {
              source.disconnect();
            } catch {
              /* already disconnected */
            }
            ttsScheduledSourcesRef.current = ttsScheduledSourcesRef.current.filter((item) => item !== source);
            endedCount += 1;
            finishIfComplete();
          };
          source.start(startAt);
        };

        const handleLine = async (line: string) => {
          const trimmed = line.trim();
          if (!trimmed) return;
          const payload = JSON.parse(trimmed) as TtsStreamEvent;
          if (payload.type === "audio_chunk") {
            await scheduleChunk(payload.audio_base64 ?? "");
            return;
          }
          if (payload.type === "done") {
            streamDone = true;
            finishIfComplete();
          }
        };

        while (ttsGenerationRef.current === generation) {
          const { done, value } = await reader.read();
          bufferText += decoder.decode(value, { stream: !done });
          const lines = bufferText.split("\n");
          bufferText = lines.pop() ?? "";
          for (const line of lines) {
            await handleLine(line);
          }
          if (done) break;
        }

        if (bufferText.trim()) {
          await handleLine(bufferText);
        }
        streamDone = true;
        finishIfComplete();
      } catch (e) {
        if (streamController.signal.aborted || ttsGenerationRef.current !== generation) return;
        try {
          await playFullTtsFallback();
          return;
        } catch (fallbackError) {
          const fallbackMsg = fallbackError instanceof Error ? fallbackError.message : "playback failed";
          addMessage("system", `TTS playback error: ${fallbackMsg}`);
        }
        const msg = e instanceof Error ? e.message : "playback failed";
        logPerf("tts.stream_fallback", { error: msg });
        setAssistantSpeaking(false);
      } finally {
        if (ttsAbortControllerRef.current === streamController) {
          ttsAbortControllerRef.current = null;
        }
      }
    },
    [addMessage, backendBaseUrl, logPerf, stopCurrentTts, suppressMicFor],
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
      const result = await window.desktopApi.interactWithBackend(
        text,
        backendBaseUrl,
        provider,
        accessToken,
      );
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
        provider: provider ?? "default",
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
      void refreshHealth();
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
        let pcm: Int16Array;
        try {
          pcm = downsampleTo16BitPcm(nextSegment.audio, nextSegment.inputSampleRate, 16000);
        } catch {
          continue;
        }
        if (pcm.length < 8000) {
          continue;
        }
        const encodeStart = performance.now();
        const wavBytes = wavBytesFromPcm16(pcm, 16000);
        const encodedMs = performance.now() - encodeStart;
        const voiceprintActive = Boolean(voiceprintStatus?.enabled && voiceprintEnabled);
        const voiceprintWavBytes = voiceprintActive
          ? prepareVoiceprintAudio(nextSegment.audio, nextSegment.inputSampleRate)
          : null;
        const parallelStart = performance.now();
        let verifyResponse: Awaited<ReturnType<typeof window.desktopApi.verifyVoiceprint>> | null = null;
        let response: Awaited<ReturnType<typeof window.desktopApi.transcribeAudio>>;
        try {
          const transcribePromise = window.desktopApi.transcribeAudio(wavBytes, backendBaseUrl);
          if (voiceprintActive && voiceprintWavBytes) {
            const [verifyResult, transcribeResult] = await Promise.all([
              window.desktopApi.verifyVoiceprint(voiceprintWavBytes, backendBaseUrl),
              transcribePromise,
            ]);
            verifyResponse = verifyResult;
            response = transcribeResult;
          } else {
            voiceprintConsecutivePassesRef.current = 0;
            response = await transcribePromise;
          }
        } catch (parallelErr) {
          addMessage(
            "system",
            `Voice processing error: ${parallelErr instanceof Error ? parallelErr.message : String(parallelErr)}`,
          );
          voiceprintConsecutivePassesRef.current = 0;
          continue;
        }
        const parallelMs = performance.now() - parallelStart;
        if (voiceprintActive && verifyResponse) {
          if ("error" in verifyResponse) {
            addMessage("system", `Voice verification error: ${verifyResponse.error}`);
            voiceprintConsecutivePassesRef.current = 0;
            continue;
          }
          if (!verifyResponse.data.matched) {
            voiceprintConsecutivePassesRef.current = 0;
            logPerf("mic.voiceprint_reject", {
              score: verifyResponse.data.score,
              threshold: verifyResponse.data.threshold,
              parallelMs: parallelMs.toFixed(1),
              speakModeOn,
            });
            const rejectMessage = `Voice not recognized (score ${verifyResponse.data.score?.toFixed(2)} < threshold ${verifyResponse.data.threshold?.toFixed(2)}). Disable voiceprint in Settings or re-enroll.`;
            if (speakModeOn) {
              setLastHeardText("Voice not recognized.");
            } else {
              addMessage("system", rejectMessage);
            }
            continue;
          }
          if (speakModeOn) {
            voiceprintConsecutivePassesRef.current += 1;
            if (voiceprintConsecutivePassesRef.current < SPEAK_MODE_VOICEPRINT_REQUIRED_PASSES) {
              setLastHeardText("Voice recognized. Keep speaking.");
              continue;
            }
          } else {
            voiceprintConsecutivePassesRef.current = 0;
          }
        }
        const transcribeMs = parallelMs;
        if ("error" in response) {
          addMessage("system", `Transcription error: ${response.error}`);
          continue;
        }
        const transcript = (response.data.text ?? "").trim();
        if (!transcript || isMicSuppressed()) {
          continue;
        }
        // Drop likely noise artifacts: single short words (≤3 letters) that
        // are too brief to be real commands — common when TTS audio bleeds into the mic.
        const transcriptWords = transcript.replace(/[^a-zA-Z ]/g, " ").trim().split(/\s+/).filter(Boolean);
        if (transcriptWords.length === 1 && transcriptWords[0].length <= 3) {
          continue;
        }
        setLastHeardText(transcript);
        // In speak mode the user has explicitly opened a voice session — voice lock wake-word is not needed
        const commandText = sanitizeVoiceCommand(transcript, voiceLockEnabled && !speakModeOn);
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
          parallelMs: parallelMs.toFixed(1),
          transcribeMs: transcribeMs.toFixed(1),
          voiceprintActive,
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
  }, [addMessage, backendBaseUrl, isMicSuppressed, logPerf, sendText, speakModeOn, voiceLockEnabled, voiceprintEnabled, voiceprintStatus?.enabled]);

  const flushDeferredSegments = useCallback(() => {
    const deferred = deferredWhileSpeakingRef.current.splice(0);
    if (deferred.length === 0) return;
    const waitMs = Math.max(0, micSuppressUntilRef.current - Date.now()) + 150;
    window.setTimeout(() => {
      if (!micOnRef.current) return;
      for (const segment of deferred) {
        pendingLocalSegmentsRef.current.push(segment);
      }
      void processVoiceQueue();
    }, waitMs);
  }, [processVoiceQueue]);

  useEffect(() => {
    flushDeferredSegmentsRef.current = flushDeferredSegments;
  }, [flushDeferredSegments]);

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
        const chunk = new Float32Array(event.inputBuffer.getChannelData(0));
        let energy = 0;
        for (let i = 0; i < chunk.length; i += 1) {
          energy += chunk[i] * chunk[i];
        }
        const rms = Math.sqrt(energy / chunk.length);
        const assistantSpeakingNow = assistantSpeakingRef.current;

        // While Jarvis is speaking, keep capturing user audio but do not stop playback.
        if (isMicSuppressed() && !assistantSpeakingNow) {
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
            if (assistantSpeakingRef.current) {
              deferredWhileSpeakingRef.current.push({
                audio: merged,
                inputSampleRate: state.context.sampleRate,
              });
              if (speakModeOn) {
                setLastHeardText("Queued — I'll handle that after I finish speaking.");
              }
            } else {
              enqueueLocalSegment(merged, state.context.sampleRate);
            }
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
  }, [addMessage, enqueueLocalSegment, isMicSuppressed, speakModeOn]);

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
            setLastHeardText(transcript);
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
      voiceprintConsecutivePassesRef.current = 0;
      pendingLocalSegmentsRef.current = [];
      voiceWorkerActiveRef.current = false;
      localTranscribeBusyRef.current = false;
      setLocalTranscribeBusy(false);
    }
  }, [micOn]);

  useEffect(() => {
    // In speak mode, keep the mic active continuously. Turn it off when speak mode ends.
    voiceprintConsecutivePassesRef.current = 0;
    setMicOn(speakModeOn);
  }, [speakModeOn]);

  useEffect(() => {
    if (!speakModeOn) {
      setLastHeardText("");
      return;
    }
    void speakAssistant("I'm listening.");
  }, [speakAssistant, speakModeOn]);

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
    stopCurrentTts();
    void ttsAudioContextRef.current?.close();
    ttsAudioContextRef.current = null;
  }, [stopCurrentTts, stopLocalMicCapture, stopMicRecognition]);

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
      ? voiceprintEnabled ? "enabled" : "disabled"
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
    stopCurrentTts();
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
          voiceprintEnabled={voiceprintEnabled}
          voiceprintEnrollState={voiceprintEnrollState}
          enrollmentPrompt={voiceprintEnrollmentPrompt(voiceprintEnrollState)}
          enrollmentPhraseReady={enrollmentPhraseReady}
          enrollmentSubmitBusy={enrollmentSubmitBusy}
          voiceDetected={voiceDetected}
          onToggleVoiceprint={() => setVoiceprintEnabled((v) => !v)}
          onStartOrRedoVoiceprint={() => void handleStartOrRedoVoiceprint()}
          onSubmitEnrollmentPhrase={() => void submitEnrollmentPhrase()}
          onFinalizeVoiceprint={() => void finalizeVoiceprintEnrollment()}
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
              stopCurrentTts();
            }
          }}
        />
      </section>

      {speakModeOn ? (
        <SpeakModeControls
          voiceStatus={voiceStatus}
          voiceStatusLabel={voiceStatusLabel}
          assistantSpeaking={assistantSpeaking}
          lastHeardText={lastHeardText}
          voiceDetected={voiceDetected}
          micOn={micOn}
          backendOnline={health.backend.ok}
          onToggleMic={() => setMicOn((value) => !value)}
          onStopTts={stopCurrentTts}
          onExitSpeakMode={exitSpeakMode}
        />
      ) : null}

    </main>
  );
}
