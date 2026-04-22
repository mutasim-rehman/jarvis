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
  getRepoRoot: () => Promise<string>;
  onServiceLog: (callback: (payload: ServiceLogEvent) => void) => () => void;
}

declare global {
  interface Window {
    desktopApi: DesktopApi;
  }
}
