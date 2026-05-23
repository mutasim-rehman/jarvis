# JARVIS Hub

Public product website for JARVIS (Phase 7). Static Astro site with landing page, feature overview, and legal pages required for **Google OAuth** and other provider consoles.

## Pages

| Path | Purpose |
|------|---------|
| `/` | Landing — value prop, features, architecture, safety |
| `/privacy` | Privacy Policy |
| `/terms` | Terms of Service |

## Local development

```bash
cd hub
npm install
npm run dev
```

Open [http://localhost:4321](http://localhost:4321).

## Production build

Set your public URL (no trailing slash) so canonical links and OAuth console URLs match:

```bash
# PowerShell
$env:PUBLIC_SITE_URL = "https://your-domain.com"
$env:PUBLIC_CONTACT_EMAIL = "you@example.com"   # optional
npm run build
```

Output is in `hub/dist/`. Preview locally:

```bash
npm run preview
```

## Deploy

Deploy `dist/` to any static host:

- **Cloudflare Pages** — build command: `npm run build`, output: `dist`, root: `hub`
- **Vercel** — same; set `PUBLIC_SITE_URL` in project env
- **GitHub Pages** — use `astro build` with `site` set to `https://<user>.github.io/<repo>/` if serving from a subpath

## Google Cloud OAuth console

Use these URLs (replace with your production domain):

| Field | URL |
|-------|-----|
| Application home page | `https://your-domain.com/` |
| Privacy policy | `https://your-domain.com/privacy` |
| Terms of service | `https://your-domain.com/terms` |
| Authorized domains | `your-domain.com` |

For **local desktop OAuth** (e.g. Classroom), redirect URIs stay on `http://127.0.0.1` per executor docs; the hub URLs above satisfy the **product website** requirement for the OAuth consent screen.

Update `src/config/site.ts` or env vars (`PUBLIC_CONTACT_EMAIL`, `PUBLIC_GITHUB_URL`) before going live.

## Stack

- [Astro](https://astro.build/) 6.x
- [Tailwind CSS](https://tailwindcss.com/) 4.x
- Styling aligned with `controller/desktop/` (black + orange theme)
- 3D visual: `public/jarvis-visual.html` (same as `controller/desktop/src/jarvisCoreVisualHtml.ts`)

To refresh the visual after desktop changes:

```bash
cd hub
npx tsx -e "import { jarvisCoreVisualHtml } from './src/lib/jarvisCoreVisualHtml.ts'; import fs from 'fs'; fs.writeFileSync('public/jarvis-visual.html', jarvisCoreVisualHtml);"
```
