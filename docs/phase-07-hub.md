# Phase 7 — Hub (Product Website)

**Objective:** Public-facing **hub** that explains JARVIS, showcases features, hosts demos or video, and optionally links to a dashboard or download areas.

## Tech stack

| Layer | Technology |
|--------|------------|
| **Site** | [Astro](https://astro.build/) 4.x — content-focused, fast static pages; optional [React](https://react.dev/) islands for interactive demos |
| **Styling** | [Tailwind CSS](https://tailwindcss.com/) (align with `controller/desktop/` if desired) |
| **Content** | [MDX](https://mdxjs.com/) or Markdown in `src/content/` for features/docs snippets |
| **Hosting** | Static export to [Cloudflare Pages](https://pages.cloudflare.com/), [Vercel](https://vercel.com/), or [GitHub Pages](https://pages.github.com/) |
| **Demo backend (optional)** | Sandboxed FastAPI + Ollama not exposed publicly — use canned responses or rate-limited proxy; **same model family** (`llama3.2` / `llama3.3`) if live demo is required |
| **Analytics (optional)** | Privacy-friendly Plausible or similar |

## Scope

- **Landing page:** value proposition, architecture at a high level, trust/safety note for an execution system.
- **Feature pages** or sections: voice control, desktop execution, security model (high level).
- **Demos:** embedded clips, interactive demo (if backend available in a sandbox), or “try the API” with strict limits.
- **Optional dashboard:** sign-in, API keys, device pairing — only if product roadmap requires it; can remain a stub.

## Out of scope

- Core execution logic (covered in Phases 1–6).

## Deliverables

1. **`hub/`** site: static or SSR stack per team choice; deployable build.
2. **Content:** copy and visuals aligned with README and phase docs (no contradictions).
3. **Links** to source, docs, and support/contact if applicable.

## Success criteria

- A new visitor understands what JARVIS does and how it differs from a plain chatbot.
- Build and deploy steps are documented (CI optional).

## Dependencies

- None strictly; messaging improves once Phases 1–4 prove the demo story.

## Risks / notes

- Do not oversell unattended automation; align with Phase 6 limitations.
- Performance and SEO basics if the site is public marketing.
