/**
 * Wrapper-shared configuration module.
 *
 * Loads `<service>/.env` first (so service-local overrides win) and then
 * `<wrapper>/.env` (the project root) for shared DATABASE_URL / JWT_SECRET
 * and friends. Both files are optional -- sane defaults keep the skeleton
 * runnable on a bare clone.
 *
 * Exports a single `config` object with strongly-typed accessors so
 * handlers do not have to repeatedly probe `process.env`.
 */

const { existsSync } = require('node:fs');
const { resolve, dirname } = require('node:path');
const dotenv = require('dotenv');

// Walk up one directory from `src/` (the package root) to find the
// wrapper-level `.env` shipped by `_skels/_common/common-wrapper.sh`.
const SERVICE_ROOT = resolve(__dirname, '..');
const LOCAL_ENV = resolve(SERVICE_ROOT, '.env');
const WRAPPER_ENV = resolve(SERVICE_ROOT, '..', '.env');

// Local `.env` is loaded FIRST. dotenv does not overwrite existing keys
// by default, so values defined locally win over the wrapper-shared
// values loaded right after.
if (existsSync(LOCAL_ENV)) {
  dotenv.config({ path: LOCAL_ENV });
}
if (existsSync(WRAPPER_ENV)) {
  dotenv.config({ path: WRAPPER_ENV });
}

function intFromEnv(name, fallback) {
  const raw = process.env[name];
  if (raw === undefined || raw === '') {
    return fallback;
  }
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/**
 * Extract the SQLite file path from a DATABASE_URL.
 * Handles `sqlite:///path/to/db` (absolute) and `sqlite:///./rel` (relative).
 * Returns null for non-sqlite URLs.
 */
function dbPathFromUrl(url) {
  if (!url) return null;
  if (url.startsWith('sqlite:///')) {
    return url.slice('sqlite:///'.length);
  }
  if (url.startsWith('sqlite://')) {
    return url.slice('sqlite://'.length);
  }
  return null;
}

const databaseUrl = process.env.DATABASE_URL || 'sqlite:///./data/service.db';

const config = {
  databaseUrl,
  dbPath: dbPathFromUrl(databaseUrl) || './data/service.db',
  jwt: {
    secret: process.env.JWT_SECRET || 'change-me-32-bytes-of-random-data',
    algorithm: process.env.JWT_ALGORITHM || 'HS256',
    issuer: process.env.JWT_ISSUER || 'devskel',
    accessTtl: intFromEnv('JWT_ACCESS_TTL', 3600),
    refreshTtl: intFromEnv('JWT_REFRESH_TTL', 604800),
  },
  service: {
    host: process.env.SERVICE_HOST || '0.0.0.0',
    port: intFromEnv('SERVICE_PORT', intFromEnv('PORT', 3000)),
  },
  seed: [
    // Regular user account (from USER_* env vars)
    ...(process.env.USER_LOGIN
      ? [{
          username: process.env.USER_LOGIN,
          email: process.env.USER_EMAIL || null,
          password: process.env.USER_PASSWORD || '',
        }]
      : []),
    // Superuser account (from SUPERUSER_* env vars)
    ...(process.env.SUPERUSER_LOGIN
      ? [{
          username: process.env.SUPERUSER_LOGIN,
          email: process.env.SUPERUSER_EMAIL || null,
          password: process.env.SUPERUSER_PASSWORD || '',
        }]
      : []),
  ],
};

module.exports = { config, dbPathFromUrl };
