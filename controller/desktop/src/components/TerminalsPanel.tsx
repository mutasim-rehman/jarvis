import type { TerminalSnapshot } from "../desktop-api";

type TerminalsPanelProps = {
  terminals: TerminalSnapshot[];
  loading: boolean;
  onRefresh: () => void;
  onClose: () => void;
};

export function TerminalsPanel({ terminals, loading, onRefresh, onClose }: TerminalsPanelProps) {
  const running = terminals.filter((terminal) => {
    if (terminal.activeCommand.trim()) return true;
    return terminal.lastExitCode === "" || terminal.lastExitCode === "null";
  });

  return (
    <section className="terminals-panel">
      <header>
        <h3>Running Terminals</h3>
        <div className="panel-header-actions">
          <button type="button" onClick={onRefresh} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh list"}
          </button>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </header>
      <div className="terminal-items">
        {running.length === 0 ? (
          <p className="terminal-empty">No running terminals found.</p>
        ) : (
          running.map((terminal) => (
            <article key={terminal.id} className="terminal-item">
              <strong>#{terminal.id}</strong>
              <span>{terminal.cwd || "(cwd unavailable)"}</span>
              <code>{terminal.activeCommand || terminal.lastCommand || "(no command recorded)"}</code>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
