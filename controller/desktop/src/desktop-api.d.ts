export type ServiceId = "backend" | "executor" | "cli";

export interface ServiceStatus {
  id: ServiceId;
  name: string;
  command: string;
  running: boolean;
  pid: number | null;
  startedAt: number | null;
  logs: string[];
}

export interface HealthResponse {
  ok: boolean;
  status: number;
  data?: {
    stt_ready?: boolean;
    tts_ready?: boolean;
    [key: string]: unknown;
  };
  error?: string;
}

export interface ServiceLogEvent {
  serviceId: ServiceId;
  line: string;
}

export interface JarvisProfile {
  identity?: {
    name?: string;
    addressing_style?: {
      primary?: string;
    };
  };
  voice_profile?: {
    speed?: number;
    pitch?: string;
    type?: string;
    accent?: string;
  };
  interaction_rules?: {
    greetings?: string[];
  };
}

export interface TerminalSnapshot {
  id: string;
  pid: number | null;
  cwd: string;
  activeCommand: string;
  lastCommand: string;
  lastExitCode: string;
}

export interface VoiceprintStatus {
  enabled: boolean;
  samples_collected: number;
  min_required_samples: number;
  target_samples?: number;
  threshold: number;
  enrollment_phrases: string[];
  next_enrollment_phrase: string;
}

export interface VoiceprintVerifyResult {
  matched: boolean;
  score: number;
  threshold: number;
  enabled: boolean;
}

interface DesktopApi {
  listServices: () => Promise<ServiceStatus[]>;
  startService: (serviceId: ServiceId) => Promise<ServiceStatus>;
  stopService: (serviceId: ServiceId) => Promise<ServiceStatus>;
  startAllServices: () => Promise<{ services: ServiceStatus[]; errors: string[] }>;
  stopAllServices: () => Promise<ServiceStatus[]>;
  checkServiceHealth: (serviceId: ServiceId) => Promise<HealthResponse>;
  getServiceBaseUrl: (serviceId: ServiceId) => Promise<string>;
  setAuthSession: (
    accessToken: string | null,
    deviceId: string | null,
  ) => Promise<{ ok: true }>;
  startOAuthListener: () => Promise<{ ok: true; port?: number } | { ok: false; error: string }>;
  openExternalUrl: (url: string) => Promise<{ ok: true } | { ok: false; error: string }>;
  openOAuthWindow: (
    oauthUrl: string,
  ) => Promise<{ ok: true; callbackUrl: string } | { ok: false; error: string }>;
  onOAuthCallback: (callback: (callbackUrl: string) => void) => () => void;
  interactWithBackend: (
    text: string,
    baseUrl: string,
    chatProvider?: "huggingface" | "ollama",
    accessToken?: string | null,
  ) => Promise<{ ok: true; data: unknown } | { ok: false; error: string }>;
  transcribeAudio: (
    wavBytes: Uint8Array,
    baseUrl: string,
  ) => Promise<{ ok: true; data: { text?: string } } | { ok: false; error: string }>;
  synthesizeSpeech: (
    text: string,
    baseUrl: string,
  ) => Promise<
    | { ok: true; data: { audio_base64?: string; sample_rate?: number; format?: string; voice?: string } }
    | { ok: false; error: string }
  >;
  getVoiceprintStatus: (baseUrl: string) => Promise<{ ok: true; data: VoiceprintStatus } | { ok: false; error: string }>;
  resetVoiceprint: (baseUrl: string) => Promise<{ ok: true; data: VoiceprintStatus } | { ok: false; error: string }>;
  enrollVoiceprintSample: (
    wavBytes: Uint8Array,
    baseUrl: string,
  ) => Promise<
    | {
        ok: true;
        data: {
          samples_collected: number;
          min_required_samples: number;
          target_samples?: number;
          ready_to_finalize: boolean;
          enrollment_phrases: string[];
          next_enrollment_phrase: string;
        };
      }
    | { ok: false; error: string }
  >;
  finalizeVoiceprint: (baseUrl: string) => Promise<{ ok: true; data: VoiceprintStatus } | { ok: false; error: string }>;
  verifyVoiceprint: (
    wavBytes: Uint8Array,
    baseUrl: string,
  ) => Promise<{ ok: true; data: VoiceprintVerifyResult } | { ok: false; error: string }>;
  getRepoRoot: () => Promise<string>;
  getJarvisProfile: () => Promise<{ ok: true; data: JarvisProfile } | { ok: false; error: string }>;
  listTerminals: () => Promise<
    { ok: true; data: TerminalSnapshot[] } | { ok: false; error: string; data: TerminalSnapshot[] }
  >;
  onServiceLog: (callback: (payload: ServiceLogEvent) => void) => () => void;
  openDevTools: () => Promise<{ ok: true } | { ok: false; error: string }>;
}

declare global {
  interface Window {
    desktopApi: DesktopApi;
  }
}
