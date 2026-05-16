export type ConversationRole = "user" | "assistant" | "system";

export type ConversationMessage = {
  id: string;
  role: ConversationRole;
  text: string;
  createdAt: number;
};
