const WAKE_WORD_REGEX = /^(?:hey\s+|ok\s+)?jarvis[\s,.:!-]*/i;

export function voiceprintEnrollmentPrompt(state: {
  active: boolean;
  samplesCollected: number;
  minRequired: number;
  enrollmentPhrases: string[];
}): string | null {
  if (!state.active || state.enrollmentPhrases.length === 0) return null;
  if (state.samplesCollected >= state.minRequired) return null;
  const idx = Math.min(state.samplesCollected, state.enrollmentPhrases.length - 1);
  return state.enrollmentPhrases[idx] ?? null;
}

export function sanitizeVoiceCommand(rawTranscript: string, requireWakeWord: boolean): string | null {
  const cleaned = rawTranscript.trim().replace(/\s+/g, " ");
  if (!cleaned) return null;
  if (!requireWakeWord) return cleaned;
  if (!WAKE_WORD_REGEX.test(cleaned)) return null;
  const withoutWakeWord = cleaned.replace(WAKE_WORD_REGEX, "").trim();
  return withoutWakeWord || null;
}
