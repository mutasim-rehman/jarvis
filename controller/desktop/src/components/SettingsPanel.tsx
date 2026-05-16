import type { VoiceprintStatus } from "../desktop-api";

type VoiceprintEnrollState = {
  active: boolean;
  samplesCollected: number;
  minRequired: number;
  enrollmentPhrases: string[];
};

type SettingsPanelProps = {
  voiceprintStatus: VoiceprintStatus | null;
  voiceprintEnrollState: VoiceprintEnrollState;
  enrollmentPrompt: string | null;
  onStartOrRedoVoiceprint: () => void;
  onRefresh: () => void;
  onOpenDevTools: () => void;
  onClose: () => void;
};

export function SettingsPanel({
  voiceprintStatus,
  voiceprintEnrollState,
  enrollmentPrompt,
  onStartOrRedoVoiceprint,
  onRefresh,
  onOpenDevTools,
  onClose,
}: SettingsPanelProps) {
  return (
    <section className="settings-panel">
      <header>
        <h3>Settings</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </header>

      <article className="settings-item settings-dev-item">
        <strong>Developer</strong>
        <div className="settings-dev-actions">
          <button type="button" title="Refresh service health and status" onClick={onRefresh}>
            Refresh status
          </button>
          <button type="button" title="Open Electron developer tools" onClick={onOpenDevTools}>
            DevTools
          </button>
        </div>
      </article>

      <article className="settings-item">
        <div>
          <strong>Voice Print</strong>
          <p>
            {voiceprintEnrollState.active
              ? `Enrollment in progress: ${voiceprintEnrollState.samplesCollected}/${voiceprintEnrollState.minRequired}`
              : voiceprintStatus?.enabled
                ? "Voice verification enabled."
                : "Not enrolled yet."}
          </p>
          <p className="voiceprint-prompt">
            {voiceprintEnrollState.active ? (
              <>
                Phrase {Math.min(voiceprintEnrollState.samplesCollected + 1, voiceprintEnrollState.minRequired)} of{" "}
                {voiceprintEnrollState.minRequired}: <q>{enrollmentPrompt ?? "…"}</q>
              </>
            ) : voiceprintStatus?.enabled ? (
              <>Each command segment is checked against your voice. Speak naturally; no fixed passphrase is required.</>
            ) : (
              <>
                Enrollment records {voiceprintStatus?.min_required_samples ?? "several"} different phrases so the
                model hears varied sounds—not one replayable line.
              </>
            )}
          </p>
        </div>
        <button type="button" onClick={onStartOrRedoVoiceprint}>
          {voiceprintStatus?.enabled || voiceprintEnrollState.active ? "Redo Voice Print" : "Start Voice Print"}
        </button>
      </article>
    </section>
  );
}
