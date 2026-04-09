import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { defineConfig } from 'vitest/config';
import { loadEnv } from 'vite';
import react from '@vitejs/plugin-react-swc';

/**
 * Load the wrapper-shared `<project>/.env` (one level up from this
 * service directory) plus the auto-generated
 * `<project>/_shared/service-urls.env`, then re-export only the safe
 * subset of variables as `VITE_*` so they reach `import.meta.env` at
 * build time.
 *
 * NEVER expose `JWT_SECRET` here — secrets must stay on the backends.
 * The frontend only needs the API base URL, the JWT issuer (for
 * audience checks), and the per-service URLs the wrapper allocated.
 */
function loadWrapperEnv(serviceDir: string): Record<string, string> {
  const wrapperDir = dirname(serviceDir);
  const wrapperEnvPath = resolve(wrapperDir, '.env');
  const serviceUrlsPath = resolve(wrapperDir, '_shared', 'service-urls.env');

  const collected: Record<string, string> = {};

  for (const candidate of [wrapperEnvPath, serviceUrlsPath]) {
    if (!existsSync(candidate)) continue;
    const text = readFileSync(candidate, 'utf-8');
    for (const rawLine of text.split('\n')) {
      const line = rawLine.trim();
      if (!line || line.startsWith('#')) continue;
      const eq = line.indexOf('=');
      if (eq <= 0) continue;
      const key = line.slice(0, eq).trim();
      const value = line.slice(eq + 1).trim().replace(/^["']|["']$/g, '');
      collected[key] = value;
    }
  }

  // Whitelist of safe keys promoted to VITE_* (do NOT add JWT_SECRET).
  const exported: Record<string, string> = {};
  const safeKeys = [
    'JWT_ALGORITHM',
    'JWT_ISSUER',
    'JWT_ACCESS_TTL',
    'JWT_REFRESH_TTL',
    'SERVICE_HOST',
    'SERVICE_PORT_BASE',
  ];
  for (const key of safeKeys) {
    if (collected[key]) {
      exported[`VITE_WRAPPER_${key}`] = collected[key];
    }
  }
  for (const [key, value] of Object.entries(collected)) {
    if (key.startsWith('SERVICE_URL_') || key.startsWith('SERVICE_PORT_')) {
      exported[`VITE_WRAPPER_${key}`] = value;
    }
  }

  // VITE_BACKEND_URL — explicit pointer to the default backend the
  // frontend should call. Resolution order:
  //   1. Explicit `VITE_BACKEND_URL` already in the local .env.
  //   2. Wrapper-shared `BACKEND_URL` from <wrapper>/.env.
  //   3. First `SERVICE_URL_*` in alphabetical order from
  //      `_shared/service-urls.env`.
  //   4. Hard-coded `http://localhost:8000` (the django-bolt default).
  const firstServiceUrl = Object.entries(collected)
    .filter(([k]) => k.startsWith('SERVICE_URL_'))
    .sort(([a], [b]) => a.localeCompare(b))[0];
  exported['VITE_BACKEND_URL'] =
    collected['VITE_BACKEND_URL'] ||
    collected['BACKEND_URL'] ||
    (firstServiceUrl ? firstServiceUrl[1] : 'http://localhost:8000');

  // Backwards-compatible alias retained for projects that already
  // import `config.apiBaseUrl`. Point it at the same value so the
  // two stay in sync.
  exported['VITE_API_BASE_URL'] = exported['VITE_BACKEND_URL'];

  return exported;
}

export default defineConfig(({ mode }) => {
  const serviceDir = process.cwd();
  const wrapperEnv = loadWrapperEnv(serviceDir);
  // Merge with the per-service Vite envs (`.env`, `.env.local`, ...) so
  // local overrides still win — Vite's loadEnv already returns the
  // service-level values; the spread below makes wrapper values fill
  // in any keys the local files do not define.
  const localEnv = loadEnv(mode, serviceDir, 'VITE_');
  const merged = { ...wrapperEnv, ...localEnv };

  return {
    plugins: [react()],
    define: Object.fromEntries(
      Object.entries(merged).map(([key, value]) => [
        `import.meta.env.${key}`,
        JSON.stringify(value),
      ])
    ),
    server: {
      port: 5173,
      open: true,
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/setupTests.ts',
    },
  };
});
