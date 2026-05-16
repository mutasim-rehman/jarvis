import { useCallback, useEffect, useRef, useState } from "react";
import type { ConversationMessage } from "../types/conversation";
import { ChatControls } from "./ChatControls";
import { ChatMessage } from "./ChatMessage";

type ConversationPaneProps = {
  hidden: boolean;
  activeBotLabel: string;
  voiceprintSummary: string;
  backendOnline: boolean;
  messages: ConversationMessage[];
  chatInput: string;
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

export function ConversationPane({
  hidden,
  activeBotLabel,
  voiceprintSummary,
  backendOnline,
  messages,
  chatInput,
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
}: ConversationPaneProps) {
  const messagesRef = useRef<HTMLDivElement>(null);
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const el = messagesRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
    setShowScrollBottom(false);
  }, []);

  useEffect(() => {
    if (!showScrollBottom) {
      scrollToBottom("auto");
    }
  }, [messages, showScrollBottom, scrollToBottom]);

  const handleMessagesScroll = () => {
    const el = messagesRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollBottom(distanceFromBottom > 48);
  };

  return (
    <aside className={`conversation-pane ${hidden ? "hidden" : ""}`}>
      <h2>Jarvis Conversation</h2>
      <p className="conversation-meta">Active chat mode: {activeBotLabel}</p>
      <p className="conversation-meta">Voiceprint: {voiceprintSummary}</p>

      {!backendOnline ? (
        <p className="offline-banner" role="status">
          Services offline — start Jarvis to chat
        </p>
      ) : null}

      <div className="messages-wrap">
        <div ref={messagesRef} className="messages" onScroll={handleMessagesScroll}>
          {messages.length === 0 ? (
            <div className="conversation-empty">
              <p className="empty-title">Ready when you are</p>
              <p className="empty-hint">Try: &quot;Jarvis, play some music&quot;</p>
              <p className="empty-hint">Or: &quot;Jarvis, what&apos;s the weather?&quot;</p>
              <p className="empty-hint">Type below or tap Mic to speak</p>
            </div>
          ) : (
            messages.map((message) => <ChatMessage key={message.id} message={message} />)
          )}
        </div>

        {showScrollBottom ? (
          <button
            type="button"
            className="scroll-to-bottom"
            title="Scroll to latest messages"
            onClick={() => scrollToBottom()}
          >
            ↓ New messages
          </button>
        ) : null}
      </div>

      <ChatControls
        chatInput={chatInput}
        backendOnline={backendOnline}
        inFlightChat={inFlightChat}
        micOn={micOn}
        voiceLockEnabled={voiceLockEnabled}
        speakModeOn={speakModeOn}
        voiceDetected={voiceDetected}
        onInputChange={onInputChange}
        onSubmit={onSubmit}
        onToggleMic={onToggleMic}
        onToggleVoiceLock={onToggleVoiceLock}
        onToggleSpeakMode={onToggleSpeakMode}
      />
    </aside>
  );
}
