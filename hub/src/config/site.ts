/** Public site metadata — update before production deploy / Google OAuth console. */
export const site = {
  name: "JARVIS",
  tagline: "Understand. Decide. Execute.",
  description:
    "JARVIS turns natural language into structured intent and runs real tasks on your desktop—an execution system, not a chatbot.",
  shortDescription:
    "Distributed AI assistant for voice, intent planning, and safe desktop execution.",
  /** Used in legal pages and OAuth console; override with PUBLIC_CONTACT_EMAIL at build time if needed. */
  contactEmail:
    import.meta.env.PUBLIC_CONTACT_EMAIL ?? "support@jarvis.app",
  githubUrl: import.meta.env.PUBLIC_GITHUB_URL ?? "",
  docsUrl: import.meta.env.PUBLIC_DOCS_URL ?? "",
} as const;
