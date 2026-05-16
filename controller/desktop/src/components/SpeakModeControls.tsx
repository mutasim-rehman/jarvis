type SpeakModeControlsProps = {
  voiceStatus: "idle" | "listening" | "processing" | "speaking";
  voiceStatusLabel: string;
  micOn: boolean;
  backendOnline: boolean;
  onToggleMic: () => void;
  onExitSpeakMode: () => void;
};

export function SpeakModeControls({
  voiceStatus,
  voiceStatusLabel,
  micOn,
  backendOnline,
  onToggleMic,
  onExitSpeakMode,
}: SpeakModeControlsProps) {
  return (
    <div className="speak-floating-controls">
      <span className={`voice-indicator ${voiceStatus}`}>{voiceStatusLabel}</span>
      <button
        type="button"
        className={`mic-button ${micOn ? "active" : ""}`}
        disabled={!backendOnline}
        title={micOn ? "Turn microphone off" : "Turn microphone on"}
        onClick={onToggleMic}
      >
        {micOn ? "Mic On" : "Mic Off"}
      </button>
      <button type="button" className="speak-floating" onClick={onExitSpeakMode}>
        Speak Off
      </button>
    </div>
  );
}
