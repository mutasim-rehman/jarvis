import type { ConversationMessage } from "../types/conversation";
import { formatRelativeTime } from "../utils/relativeTime";

const ROLE_LABELS: Record<ConversationMessage["role"], string> = {
  user: "You",
  assistant: "Jarvis",
  system: "System",
};

type ChatMessageProps = {
  message: ConversationMessage;
};

export function ChatMessage({ message }: ChatMessageProps) {
  return (
    <article className={`message ${message.role}`}>
      <header className="message-header">
        <strong>{ROLE_LABELS[message.role]}</strong>
        <time className="message-time" dateTime={new Date(message.createdAt).toISOString()}>
          {formatRelativeTime(message.createdAt)}
        </time>
      </header>
      <p>{message.text}</p>
    </article>
  );
}
