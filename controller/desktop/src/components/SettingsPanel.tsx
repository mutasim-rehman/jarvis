import { useState } from "react";
import type { VoiceprintStatus } from "../desktop-api";
import { useAuth } from "../auth/AuthProvider";
import { deleteAccount } from "../lib/backendApi";
import { ensureBackendRunning, formatBackendError, resolveBackendBaseUrl } from "../lib/backendReady";
import { ConfirmModal } from "./ConfirmModal";

type VoiceprintEnrollState = {
  active: boolean;
  samplesCollected: number;
  minRequired: number;
  enrollmentPhrases: string[];
  canFinalize: boolean;
};

type SettingsPanelProps = {
  voiceprintStatus: VoiceprintStatus | null;
  voiceprintEnabled: boolean;
  voiceprintEnrollState: VoiceprintEnrollState;
  enrollmentPrompt: string | null;
  enrollmentPhraseReady: boolean;
  enrollmentSubmitBusy: boolean;
  voiceDetected: boolean;
  onToggleVoiceprint: () => void;
  onStartOrRedoVoiceprint: () => void;
  onSubmitEnrollmentPhrase: () => void;
  onFinalizeVoiceprint: () => void;
  onRefresh: () => void;
  onOpenDevTools: () => void;
  onClose: () => void;
};

export function SettingsPanel({
  voiceprintStatus,
  voiceprintEnabled,
  voiceprintEnrollState,
  enrollmentPrompt,
  enrollmentPhraseReady,
  enrollmentSubmitBusy,
  voiceDetected,
  onToggleVoiceprint,
  onStartOrRedoVoiceprint,
  onSubmitEnrollmentPhrase,
  onFinalizeVoiceprint,
  onRefresh,
  onOpenDevTools,
  onClose,
}: SettingsPanelProps) {
  const { me, session, supabaseEnabled, signOut, resolveAccessToken } = useAuth();
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [accountBusy, setAccountBusy] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);

  const handleDeleteAccount = async () => {
    setAccountBusy(true);
    setAccountError(null);
    let baseUrl = await resolveBackendBaseUrl();
    try {
      const token = await resolveAccessToken();
      if (!token) {
        throw new Error("Not signed in.");
      }
      baseUrl = await ensureBackendRunning();
      await deleteAccount(baseUrl, token);
      await signOut();
      setDeleteConfirmOpen(false);
      onClose();
    } catch (err) {
      setAccountError(formatBackendError(err, baseUrl));
      setDeleteConfirmOpen(false);
    } finally {
      setAccountBusy(false);
    }
  };

  return (
    <section className="settings-panel">
      <header>
        <h3>Settings</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </header>

      {supabaseEnabled && session ? (
        <article className="settings-item settings-account-item">
          <strong>Account</strong>
          <p>{me?.email ?? session.user.email ?? "Signed in"}</p>
          {accountError ? <p className="settings-account-error">{accountError}</p> : null}
          <div className="settings-account-actions">
            <button type="button" disabled={accountBusy} onClick={() => void signOut()}>
              Sign out
            </button>
            <button
              type="button"
              className="settings-danger-btn"
              disabled={accountBusy}
              onClick={() => setDeleteConfirmOpen(true)}
            >
              Delete account
            </button>
          </div>
        </article>
      ) : null}

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
              ? voiceprintEnrollState.canFinalize
                ? `Required enrollment complete: ${voiceprintEnrollState.samplesCollected}/${voiceprintEnrollState.enrollmentPhrases.length || voiceprintEnrollState.minRequired}`
                : `Enrollment in progress: ${voiceprintEnrollState.samplesCollected}/${voiceprintEnrollState.minRequired}`
              : voiceprintStatus?.enabled
                ? voiceprintEnabled
                  ? "Voice verification active."
                  : "Voice verification enrolled but disabled."
                : "Not enrolled yet."}
          </p>
          <p className="voiceprint-prompt">
            {voiceprintEnrollState.active ? (
              <>
                Phrase{" "}
                {Math.min(
                  voiceprintEnrollState.samplesCollected + 1,
                  voiceprintEnrollState.enrollmentPhrases.length || voiceprintEnrollState.minRequired,
                )}{" "}
                of {voiceprintEnrollState.enrollmentPhrases.length || voiceprintEnrollState.minRequired}:{" "}
                <q>{enrollmentPrompt ?? "…"}</q>
                {voiceprintEnrollState.samplesCollected >= voiceprintEnrollState.minRequired ? (
                  <> Optional room calibration helps speak mode in noisy places.</>
                ) : null}
              </>
            ) : voiceprintStatus?.enabled ? (
              voiceprintEnabled ? (
                <>Each command segment is checked against your voice. Speak naturally; no fixed passphrase is required.</>
              ) : (
                <>Verification is paused. Commands are accepted from any voice. Re-enable to restore speaker check.</>
              )
            ) : (
              <>
                Enrollment records {voiceprintStatus?.min_required_samples ?? "several"} different phrases so the
                model hears varied sounds—not one replayable line.
              </>
            )}
          </p>
          {voiceprintEnrollState.active ? (
            <div className="voiceprint-enroll-actions">
              <p className="voiceprint-enroll-hint">
                Speak the phrase at your own pace. Short pauses are fine—when you are completely done with this
                phrase, tap Submit phrase. After the required phrases, add the optional room samples where you
                normally use speak mode, or finish enrollment.
              </p>
              {voiceDetected ? (
                <p className="voiceprint-enroll-status" role="status">
                  Hearing you…
                </p>
              ) : null}
              <button
                type="button"
                className="voiceprint-submit-phrase"
                disabled={!enrollmentPhraseReady || enrollmentSubmitBusy}
                onClick={onSubmitEnrollmentPhrase}
              >
                {enrollmentSubmitBusy ? "Submitting…" : "Submit phrase"}
              </button>
              {voiceprintEnrollState.canFinalize ? (
                <button type="button" className="voiceprint-submit-phrase" onClick={onFinalizeVoiceprint}>
                  Finish enrollment
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="voiceprint-actions">
          {voiceprintStatus?.enabled && !voiceprintEnrollState.active ? (
            <button
              type="button"
              className={voiceprintEnabled ? "voiceprint-toggle-off" : "voiceprint-toggle-on"}
              onClick={onToggleVoiceprint}
            >
              {voiceprintEnabled ? "Disable" : "Enable"}
            </button>
          ) : null}
          <button type="button" onClick={onStartOrRedoVoiceprint}>
            {voiceprintStatus?.enabled || voiceprintEnrollState.active ? "Redo" : "Start enrollment"}
          </button>
        </div>
      </article>

      <ConfirmModal
        open={deleteConfirmOpen}
        title="Delete account"
        message="This permanently deletes your preferences, personality profile, device links, and tasks. This cannot be undone."
        confirmLabel={accountBusy ? "Deleting…" : "Delete account"}
        cancelLabel="Cancel"
        confirmVariant="danger"
        onConfirm={() => void handleDeleteAccount()}
        onCancel={() => {
          if (!accountBusy) setDeleteConfirmOpen(false);
        }}
      />
    </section>
  );
}
