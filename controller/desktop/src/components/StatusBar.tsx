type BackendBadge = {
  className: "ok" | "warn" | "error";
  label: string;
};

type StatusBarProps = {
  settingsOpen: boolean;
  areAllCoreRunning: boolean;
  activeBotLabel: string;
  backendBadge: BackendBadge;
  executorOnline: boolean;
  onToggleSettings: () => void;
  onStartStopJarvis: () => void;
  onToggleTerminals: () => void;
  onToggleServiceLogs: () => void;
  onCycleBotMode: () => void;
};

export function StatusBar({
  settingsOpen,
  areAllCoreRunning,
  activeBotLabel,
  backendBadge,
  executorOnline,
  onToggleSettings,
  onStartStopJarvis,
  onToggleTerminals,
  onToggleServiceLogs,
  onCycleBotMode,
}: StatusBarProps) {
  return (
    <div className="top-bar">
      <button
        type="button"
        className={`icon-button ${settingsOpen ? "active" : ""}`}
        aria-label="Open settings"
        title="Settings"
        onClick={onToggleSettings}
      >
        <span aria-hidden="true">⚙</span>
      </button>
      <button type="button" title="Start or stop backend and executor services" onClick={onStartStopJarvis}>
        {areAllCoreRunning ? "Stop Jarvis" : "Start Jarvis"}
      </button>
      <button type="button" title="Show running terminal sessions" onClick={onToggleTerminals}>
        Terminals
      </button>
      <button type="button" title="Show service log output" onClick={onToggleServiceLogs}>
        Logs
      </button>
      <button type="button" title="Cycle chat provider" onClick={onCycleBotMode}>
        {activeBotLabel}
      </button>
      <span className={`badge ${backendBadge.className}`}>Backend: {backendBadge.label}</span>
      <span className={`badge ${executorOnline ? "ok" : "error"}`}>
        Executor: {executorOnline ? "Online" : "Offline"}
      </span>
    </div>
  );
}
