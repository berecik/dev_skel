/**
 * Frontend view of the wrapper-shared environment.
 *
 * Values are baked into the bundle by `vite.config.ts` at build time
 * (which loads `<wrapper>/.env` plus `<wrapper>/_shared/service-urls.env`
 * and re-exports the safe subset). To use a value at runtime, import
 * `config` from this module — never reach into `import.meta.env`
 * directly in components.
 *
 * IMPORTANT: only public values are exposed. `JWT_SECRET` is **not**
 * promoted into the frontend bundle and must never be referenced here.
 */

interface AppConfig {
  /**
   * URL of the default backend the frontend should call. Comes from
   * `BACKEND_URL` in `<wrapper>/.env` (resolved at build time by the
   * Vite plugin in `vite.config.ts`). Compose endpoints as
   * `${config.backendUrl}/api/...`.
   *
   * Defaults to `http://localhost:8000` (the django-bolt convention).
   */
  backendUrl: string;
  /**
   * Backwards-compatible alias for `backendUrl`. Existing code that
   * imports `config.apiBaseUrl` keeps working — both names point at
   * the same value.
   */
  apiBaseUrl: string;
  jwt: {
    algorithm: string;
    issuer: string;
    accessTtl: number;
    refreshTtl: number;
  };
  /**
   * Map of slugged service names → URLs (e.g.
   * `services.ticket_service` is `http://localhost:8000`). Populated by
   * the wrapper's `_shared/service-urls.env`.
   */
  services: Record<string, string>;
}

function readEnv(key: string, fallback = ''): string {
  // `import.meta.env` is statically replaced at build time, so the
  // bracket access is type-safe even though TypeScript cannot see the
  // dynamic keys defined by `vite.config.ts`.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const value = (import.meta.env as any)[key];
  return typeof value === 'string' && value.length > 0 ? value : fallback;
}

function readEnvInt(key: string, fallback: number): number {
  const raw = readEnv(key, '');
  if (!raw) return fallback;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function collectServiceUrls(): Record<string, string> {
  const out: Record<string, string> = {};
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const env = import.meta.env as Record<string, any>;
  for (const key of Object.keys(env)) {
    if (!key.startsWith('VITE_WRAPPER_SERVICE_URL_')) continue;
    const slug = key
      .slice('VITE_WRAPPER_SERVICE_URL_'.length)
      .toLowerCase();
    out[slug] = String(env[key]);
  }
  return out;
}

// `VITE_BACKEND_URL` is the canonical pointer; `VITE_API_BASE_URL` is
// the legacy alias kept in sync by the Vite plugin so both names work.
const resolvedBackendUrl = readEnv(
  'VITE_BACKEND_URL',
  readEnv('VITE_API_BASE_URL', 'http://localhost:8000')
);

export const config: AppConfig = {
  backendUrl: resolvedBackendUrl,
  apiBaseUrl: resolvedBackendUrl,
  jwt: {
    algorithm: readEnv('VITE_WRAPPER_JWT_ALGORITHM', 'HS256'),
    issuer: readEnv('VITE_WRAPPER_JWT_ISSUER', 'devskel'),
    accessTtl: readEnvInt('VITE_WRAPPER_JWT_ACCESS_TTL', 3600),
    refreshTtl: readEnvInt('VITE_WRAPPER_JWT_REFRESH_TTL', 604800),
  },
  services: collectServiceUrls(),
};

export default config;
