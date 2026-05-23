// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import node from '@astrojs/node';

/** Set PUBLIC_SITE_URL when building for production (Google OAuth, canonical URLs). */
const site =
  process.env.PUBLIC_SITE_URL?.replace(/\/$/, '') || 'http://localhost:4321';

export default defineConfig({
  site,
  // Static by default; routes with `export const prerender = false` run server-side via the Node adapter.
  output: 'static',
  adapter: node({ mode: 'standalone' }),
  vite: {
    plugins: [tailwindcss()],
  },
});
