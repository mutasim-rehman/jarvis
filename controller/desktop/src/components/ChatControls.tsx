type ChatControlsProps = {
  chatInput: string;
  backendOnline: boolean;
  inFlightChat: boolean;
  micOn: boolean;
  voiceLockEnabled: boolean;
  speakModeOn: boolean;
  voiceDetected: boolean;
  onInputChange: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onToggleMic: () => void;
  onToggleVoiceLock: () => void;
  onToggleSpeakMode: () => void;
};

export function ChatControls({
  chatInput,
  backendOnline,
  inFlightChat,
  micOn,
  voiceLockEnabled,
  speakModeOn,
  voiceDetected,
  onInputChange,
  onSubmit,
  onToggleMic,
  onToggleVoiceLock,
  onToggleSpeakMode,
}: ChatControlsProps) {
  return (
    <form className="chat-controls" onSubmit={onSubmit}>
      <input
        placeholder={backendOnline ? "Enter command..." : "Start Jarvis to chat..."}
        value={chatInput}
        disabled={!backendOnline}
        onChange={(e) => onInputChange(e.target.value)}
      />
      <button type="submit" disabled={!chatInput.trim() || !backendOnline}>
        {inFlightChat ? "Sending..." : "Send"}
      </button>
      <button
        type="button"
        className={`mic-button ${micOn ? "active" : ""}`}
        disabled={!backendOnline}
        title={micOn ? "Turn microphone off" : "Turn microphone on"}
        onClick={onToggleMic}
      >
        {micOn ? (
          <>
            <span className={`sound-wave ${voiceDetected ? "active" : ""}`} aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            Mic On
          </>
        ) : (
          "Mic Off"
        )}
      </button>
      <button
        type="button"
        className={voiceLockEnabled ? "active" : ""}
        title={
          voiceLockEnabled
            ? "Wake word required: start commands with 'Jarvis'"
            : "Wake word off: speak commands without 'Jarvis'"
        }
        onClick={onToggleVoiceLock}
      >
        {voiceLockEnabled ? "Wake Word" : "Open Mic"}
      </button>
      <button
        type="button"
        className={speakModeOn ? "active" : ""}
        title={speakModeOn ? "Disable spoken replies" : "Read replies aloud"}
        onClick={onToggleSpeakMode}
      >
        {speakModeOn ? "Speak On" : "Speak"}
      </button>
    </form>
  );
}
