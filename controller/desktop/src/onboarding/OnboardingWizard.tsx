import { useState } from "react";
import {
  importPersonality,
  patchPreferences,
  type PreferenceSliders,
} from "../lib/backendApi";
import { useAuth } from "../auth/AuthProvider";

const defaultBackend = "http://127.0.0.1:8000";

const defaultSliders: PreferenceSliders = {
  honesty: 0.7,
  humor: 0.4,
  formality: 0.6,
  verbosity: 0.5,
  proactivity: 0.5,
};

export function OnboardingWizard() {
  const { refreshMe, resolveAccessToken, backendAuthError } = useAuth();
  const [step, setStep] = useState(0);
  const [sliders, setSliders] = useState<PreferenceSliders>(defaultSliders);
  const [personalityJson, setPersonalityJson] = useState("");
  const [spotifyConsent, setSpotifyConsent] = useState(false);
  const [youtubeConsent, setYoutubeConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const finish = async (skipPersonality: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const token = await resolveAccessToken();
      if (!token) {
        throw new Error("Not signed in. Please sign in again.");
      }
      if (!skipPersonality && personalityJson.trim()) {
        const doc = JSON.parse(personalityJson) as unknown;
        await importPersonality(defaultBackend, token, doc);
      }
      await patchPreferences(defaultBackend, token, {
        onboarding_completed: true,
        sliders,
        integrations: { spotify: spotifyConsent, youtube: youtubeConsent },
      });
      await refreshMe(defaultBackend);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save preferences";
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

  const copyTemplate = async () => {
    setError(null);
    try {
      const response = await fetch(
        `${defaultBackend.replace(/\/+$/, "")}/preferences/personality/template`,
      );
      if (!response.ok) {
        throw new Error(`template fetch failed: ${response.status}`);
      }
      const template = await response.json();
      setPersonalityJson(JSON.stringify(template, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load template");
    }
  };

  return (
    <main className="onboarding-screen">
      <div className="auth-card" style={{ width: "100%", maxWidth: "520px" }}>
      <h1>Welcome to JARVIS</h1>
      {backendAuthError ? (
        <p className="onboarding-error">{backendAuthError}</p>
      ) : null}
      {step === 0 ? (
        <section>
          <h2>Personality sliders</h2>
          {(["honesty", "humor", "formality", "verbosity", "proactivity"] as const).map((key) => (
            <label key={key} className="onboarding-slider">
              <span>{key}</span>
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
          ))}
          <button type="button" onClick={() => setStep(1)}>
            Next
          </button>
        </section>
      ) : null}

      {step === 1 ? (
        <section>
          <h2>Optional: AI personality import</h2>
          <p>
            Copy the template into ChatGPT or Gemini, ask it to fill the JSON about you, then paste
            here.
          </p>
          <button type="button" onClick={() => void copyTemplate()}>
            Load empty template
          </button>
          <textarea
            rows={12}
            value={personalityJson}
            onChange={(e) => setPersonalityJson(e.target.value)}
            placeholder="Paste completed personality JSON (optional)"
          />
          <button type="button" onClick={() => setStep(2)}>
            Next
          </button>
          <button type="button" onClick={() => setStep(2)}>
            Skip personality import
          </button>
        </section>
      ) : null}

      {step === 2 ? (
        <section>
          <h2>Optional integrations</h2>
          <label>
            <input
              type="checkbox"
              checked={spotifyConsent}
              onChange={(e) => setSpotifyConsent(e.target.checked)}
            />
            Connect Spotify taste data later
          </label>
          <label>
            <input
              type="checkbox"
              checked={youtubeConsent}
              onChange={(e) => setYoutubeConsent(e.target.checked)}
            />
            Import YouTube history later
          </label>
          <button type="button" disabled={busy} onClick={() => void finish(!personalityJson.trim())}>
            {busy ? "Saving…" : "Finish onboarding"}
          </button>
        </section>
      ) : null}

      {error ? <p className="onboarding-error">{error}</p> : null}
      </div>
    </main>
  );
}
