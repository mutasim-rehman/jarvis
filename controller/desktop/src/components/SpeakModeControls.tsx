type SpeakModeControlsProps = {
  voiceStatus: "idle" | "listening" | "processing" | "speaking";
  voiceStatusLabel: string;
  assistantSpeaking: boolean;
  lastHeardText: string;
  voiceDetected: boolean;
  micOn: boolean;
  backendOnline: boolean;
  onToggleMic: () => void;
  onStopTts: () => void;
  onExitSpeakMode: () => void;
};

export function SpeakModeControls({
  voiceStatus,
  voiceStatusLabel,
  assistantSpeaking,
  lastHeardText,
  voiceDetected,
  micOn,
  backendOnline,
  onToggleMic,
  onStopTts,
  onExitSpeakMode,
}: SpeakModeControlsProps) {
  return (
    <div className="speak-floating-controls">
      <div className={`voice-indicator ${voiceStatus} ${voiceDetected ? "voice-active" : ""}`}>
        <span>{voiceStatusLabel}</span>
        {lastHeardText ? <small>Heard: {lastHeardText}</small> : null}
      </div>
      <button
        type="button"
        className={`mic-button ${micOn ? "active" : ""}`}
        disabled={!backendOnline}
        title={micOn ? "Turn microphone off" : "Turn microphone on"}
        onClick={onToggleMic}
      >
        {micOn ? "Mic On" : "Mic Off"}
      </button>
      {assistantSpeaking ? (
        <button type="button" className="speak-floating" onClick={onStopTts}>
          Stop
        </button>
      ) : null}
      <button type="button" className="speak-floating" onClick={onExitSpeakMode}>
        Speak Off
      </button>
    </div>
  );
}
