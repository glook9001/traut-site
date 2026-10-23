import { defineConfig } from 'astro/config';
import { fileURLToPath } from 'node:url';
import iwebDoctype from './integrations/iweb-doctype.mjs';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));

export default defineConfig({
  site: 'https://traut.com',
  output: 'static',
  trailingSlash: 'never',
  build: { format: 'directory' },
  integrations: [iwebDoctype()],
  vite: {
    server: {
      fs: { allow: [repoRoot] },
    },
  },
});
