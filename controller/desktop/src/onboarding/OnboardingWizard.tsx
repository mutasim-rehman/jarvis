import { useState } from "react";
import {
  fetchPersonalityTemplate,
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
  const { accessToken, refreshMe } = useAuth();
  const [step, setStep] = useState(0);
  const [sliders, setSliders] = useState<PreferenceSliders>(defaultSliders);
  const [personalityJson, setPersonalityJson] = useState("");
  const [spotifyConsent, setSpotifyConsent] = useState(false);
  const [youtubeConsent, setYoutubeConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const finish = async (skipPersonality: boolean) => {
    if (!accessToken) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (!skipPersonality && personalityJson.trim()) {
        const doc = JSON.parse(personalityJson) as unknown;
        await importPersonality(defaultBackend, accessToken, doc);
      }
      await patchPreferences(defaultBackend, accessToken, {
        onboarding_completed: true,
        sliders,
        integrations: { spotify: spotifyConsent, youtube: youtubeConsent },
      });
      await refreshMe(defaultBackend);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preferences");
    } finally {
      setBusy(false);
    }
  };

  const copyTemplate = async () => {
    if (!accessToken) {
      return;
    }
    try {
      const template = await fetchPersonalityTemplate(defaultBackend, accessToken);
      setPersonalityJson(JSON.stringify(template, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load template");
    }
  };

  return (
    <main className="onboarding-screen">
      <h1>Welcome to JARVIS</h1>
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
    </main>
  );
}
