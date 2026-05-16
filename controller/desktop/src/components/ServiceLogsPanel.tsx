import type { ServiceLogEvent } from "../desktop-api";

type ServiceLogsPanelProps = {
  events: ServiceLogEvent[];
  onClear: () => void;
  onClose: () => void;
};

export function ServiceLogsPanel({ events, onClear, onClose }: ServiceLogsPanelProps) {
  return (
    <section className="service-logs-panel">
      <header>
        <h3>Service logs</h3>
        <div className="panel-header-actions">
          <button type="button" onClick={onClear}>
            Clear
          </button>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </header>
      <div className="service-log-lines">
        {events.length === 0 ? (
          <p className="terminal-empty">No log lines yet. Start services or watch for output.</p>
        ) : (
          events.map((entry, idx) => (
            <div key={`${entry.serviceId}-${idx}-${entry.line.slice(0, 24)}`} className="service-log-line">
              <span className="service-log-id">{entry.serviceId}</span>
              <code>{entry.line}</code>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
