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
  data?: unknown;
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

interface DesktopApi {
  listServices: () => Promise<ServiceStatus[]>;
  startService: (serviceId: ServiceId) => Promise<ServiceStatus>;
  stopService: (serviceId: ServiceId) => Promise<ServiceStatus>;
  startAllServices: () => Promise<ServiceStatus[]>;
  stopAllServices: () => Promise<ServiceStatus[]>;
  checkServiceHealth: (serviceId: ServiceId) => Promise<HealthResponse>;
  interactWithBackend: (
    text: string,
    baseUrl: string,
  ) => Promise<{ ok: true; data: unknown } | { ok: false; error: string }>;
  transcribeAudio: (
    wavBytesBase64: string,
    baseUrl: string,
  ) => Promise<{ ok: true; data: { text?: string } } | { ok: false; error: string }>;
  synthesizeSpeech: (
    text: string,
    baseUrl: string,
  ) => Promise<
    | { ok: true; data: { audio_base64?: string; sample_rate?: number; format?: string; voice?: string } }
    | { ok: false; error: string }
  >;
  getRepoRoot: () => Promise<string>;
  getJarvisProfile: () => Promise<{ ok: true; data: JarvisProfile } | { ok: false; error: string }>;
  onServiceLog: (callback: (payload: ServiceLogEvent) => void) => () => void;
}

declare global {
  interface Window {
    desktopApi: DesktopApi;
  }
}
