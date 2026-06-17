import { useEffect, useState } from "react";
import {
  fetchPersonalityTemplate,
  importPersonality,
  patchPreferences,
  type PreferenceSliders,
} from "../lib/backendApi";
import { useAuth } from "../auth/AuthProvider";
import {
  ensureBackendRunning,
  formatBackendError,
  resolveBackendBaseUrl,
} from "../lib/backendReady";

const defaultSliders: PreferenceSliders = {
  honesty: 0.7,
  humor: 0.4,
  formality: 0.6,
  verbosity: 0.5,
  proactivity: 0.5,
};

const STEPS = [
  { id: 0, label: "Personality" },
  { id: 1, label: "Import" },
  { id: 2, label: "Integrations" },
] as const;

const SLIDER_LABELS: Record<keyof PreferenceSliders, string> = {
  honesty: "Honesty",
  humor: "Humor",
  formality: "Formality",
  verbosity: "Verbosity",
  proactivity: "Proactivity",
};

export function OnboardingWizard() {
  const {
    refreshMe,
    markOnboardingComplete,
    resolveAccessToken,
    backendAuthError,
    backendConnecting,
    signOut,
    session,
    me,
  } = useAuth();
  const [step, setStep] = useState(0);
  const [sliders, setSliders] = useState<PreferenceSliders>(defaultSliders);
  const [personalityJson, setPersonalityJson] = useState("");
  const [spotifyConsent, setSpotifyConsent] = useState(false);
  const [youtubeConsent, setYoutubeConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void ensureBackendRunning().catch(() => {
      // Errors surface via refreshMe / backendAuthError
    });
  }, []);

  const finish = async (skipPersonality: boolean) => {
    setBusy(true);
    setError(null);
    let baseUrl = await resolveBackendBaseUrl();
    try {
      const token = await resolveAccessToken();
      if (!token) {
        throw new Error("Not signed in. Please sign in again.");
      }
      baseUrl = await ensureBackendRunning();
      if (!skipPersonality && personalityJson.trim()) {
        const doc = JSON.parse(personalityJson) as unknown;
        await importPersonality(baseUrl, token, doc);
      }
      await patchPreferences(baseUrl, token, {
        onboarding_completed: true,
        sliders,
        integrations: { spotify: spotifyConsent, youtube: youtubeConsent },
      });
      markOnboardingComplete({
        onboarding_completed: true,
        sliders,
      });
      try {
        await refreshMe(baseUrl);
      } catch {
        // Preferences saved; refresh is best-effort for profile sync
      }
    } catch (err) {
      const message = formatBackendError(err, baseUrl);
      if (message.includes("401")) {
        setError(
          "Backend could not verify your session. Check SUPABASE_JWT_SECRET in .env matches Supabase → Settings → API → JWT Secret, then restart the backend.",
        );
      } else {
        setError(message);
      }
    } finally {
      setBusy(false);
    }
  };

  const signedInAs = me?.email ?? session?.user.email ?? null;

  const handleChangeAccount = async () => {
    setError(null);
    setBusy(true);
    try {
      await signOut();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign out");
    } finally {
      setBusy(false);
    }
  };

  const copyTemplate = async () => {
    setError(null);
    let baseUrl = await resolveBackendBaseUrl();
    try {
      const token = await resolveAccessToken();
      if (!token) {
        throw new Error("Not signed in. Please sign in again.");
      }
      baseUrl = await ensureBackendRunning();
      const template = await fetchPersonalityTemplate(baseUrl, token);
      setPersonalityJson(JSON.stringify(template, null, 2));
    } catch (err) {
      setError(formatBackendError(err, baseUrl));
    }
  };

  return (
    <main className="onboarding-screen">
      <div className="onboarding-shell">
        <aside className="onboarding-sidebar">
          <div className="auth-brand">
            <span className="auth-logo" aria-hidden="true">
              J
            </span>
            <h1>Welcome to JARVIS</h1>
          </div>
          <p className="onboarding-lead">
            Set how JARVIS talks to you. You can change these later in settings.
          </p>
          {signedInAs ? (
            <p className="onboarding-signed-in">
              Signed in as <strong>{signedInAs}</strong>
            </p>
          ) : null}
          <ol className="onboarding-steps" aria-label="Onboarding progress">
            {STEPS.map((item) => (
              <li
                key={item.id}
                className={
                  item.id === step
                    ? "onboarding-step onboarding-step-active"
                    : item.id < step
                      ? "onboarding-step onboarding-step-done"
                      : "onboarding-step"
                }
              >
                <span className="onboarding-step-num">{item.id + 1}</span>
                <span>{item.label}</span>
              </li>
            ))}
          </ol>
          <button
            type="button"
            className="onboarding-change-account"
            disabled={busy}
            onClick={() => void handleChangeAccount()}
          >
            Use a different account
          </button>
        </aside>

        <div className="onboarding-panel auth-card">
          {backendAuthError ? (
            <div className="onboarding-error-panel">
              <p className="onboarding-error">{backendAuthError}</p>
              <button
                type="button"
                className="onboarding-btn-secondary"
                disabled={busy || backendConnecting}
                onClick={() => void refreshMe()}
              >
                {backendConnecting ? "Connecting…" : "Retry connection"}
              </button>
            </div>
          ) : null}

          {step === 0 ? (
            <section className="onboarding-step-content">
              <h2>Personality sliders</h2>
              <p className="onboarding-hint">Drag each slider to match your preferred assistant style.</p>
              <div className="onboarding-sliders-grid">
                {(["honesty", "humor", "formality", "verbosity", "proactivity"] as const).map(
                  (key) => (
                    <label key={key} className="onboarding-slider">
                      <span className="onboarding-slider-label">
                        <span>{SLIDER_LABELS[key]}</span>
                        <span className="onboarding-slider-value">{sliders[key].toFixed(2)}</span>
                      </span>
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        value={sliders[key]}
                        onChange={(e) =>
                          setSliders((s) => ({ ...s, [key]: Number(e.target.value) }))
                        }
                      />
                    </label>
                  ),
                )}
              </div>
              <div className="onboarding-actions">
                <button type="button" disabled={busy} onClick={() => setStep(1)}>
                  Next
                </button>
                <button
                  type="button"
                  className="onboarding-btn-secondary"
                  disabled={busy}
                  onClick={() => void handleChangeAccount()}
                >
                  Back to sign in
                </button>
              </div>
            </section>
          ) : null}

          {step === 1 ? (
            <section className="onboarding-step-content onboarding-step-import">
              <h2>Optional: AI personality import</h2>
              <div className="onboarding-import-grid">
                <div>
                  <p className="onboarding-hint">
                    Load the template, paste it into ChatGPT or Gemini, ask it to fill the JSON
                    about you, then paste the result here.
                  </p>
                  <button type="button" className="onboarding-btn-secondary" onClick={() => void copyTemplate()}>
                    Load empty template
                  </button>
                </div>
                <textarea
                  rows={10}
                  value={personalityJson}
                  onChange={(e) => setPersonalityJson(e.target.value)}
                  placeholder="Paste completed personality JSON (optional)"
                  aria-label="Personality JSON"
                />
              </div>
              <div className="onboarding-actions">
                <button type="button" onClick={() => setStep(2)}>
                  Next
                </button>
                <button type="button" className="onboarding-btn-secondary" onClick={() => setStep(2)}>
                  Skip personality import
                </button>
                <button type="button" className="onboarding-btn-secondary" onClick={() => setStep(0)}>
                  Back
                </button>
              </div>
            </section>
          ) : null}

          {step === 2 ? (
            <section className="onboarding-step-content">
              <h2>Optional integrations</h2>
              <p className="onboarding-hint">You can connect these later from settings.</p>
              <div className="onboarding-checkboxes">
                <label className="onboarding-checkbox">
                  <input
                    type="checkbox"
                    checked={spotifyConsent}
                    onChange={(e) => setSpotifyConsent(e.target.checked)}
                  />
                  <span>Connect Spotify taste data later</span>
                </label>
                <label className="onboarding-checkbox">
                  <input
                    type="checkbox"
                    checked={youtubeConsent}
                    onChange={(e) => setYoutubeConsent(e.target.checked)}
                  />
                  <span>Import YouTube history later</span>
                </label>
              </div>
              <div className="onboarding-actions">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void finish(!personalityJson.trim())}
                >
                  {busy ? "Saving…" : "Finish onboarding"}
                </button>
                <button
                  type="button"
                  className="onboarding-btn-secondary"
                  disabled={busy}
                  onClick={() => setStep(1)}
                >
                  Back
                </button>
              </div>
            </section>
          ) : null}

          {error ? <p className="onboarding-error">{error}</p> : null}
        </div>
      </div>
    </main>
  );
}
