// @ts-check
import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

/** Set PUBLIC_SITE_URL when building for production (Google OAuth, canonical URLs). */
const site =
  process.env.PUBLIC_SITE_URL?.replace(/\/$/, '') || 'http://localhost:4321';

// https://astro.build/config
export default defineConfig({
  site,
  vite: {
    plugins: [tailwindcss()],
  },
});