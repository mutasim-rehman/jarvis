// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import vercel from '@astrojs/vercel';

/** Set PUBLIC_SITE_URL when building for production (Google OAuth, canonical URLs). */
const site =
  process.env.PUBLIC_SITE_URL?.replace(/\/$/, '') || 'http://localhost:4321';

export default defineConfig({
  site,
  // Static pages by default; `/api/waitlist` uses `prerender = false` → Vercel serverless.
  output: 'static',
  adapter: vercel(),
  vite: {
    plugins: [tailwindcss()],
  },
});
