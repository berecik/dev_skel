/**
 * Wrapper-shared configuration module.
 *
 * Loads `<wrapper>/.env` first (so DATABASE_URL / JWT_SECRET and friends
 * are inherited from the project root) and then the local service `.env`
 * for service-specific overrides. Both files are optional — sane defaults
 * keep the skeleton runnable on a bare clone.
 *
 * Exports a single `config` object with strongly-typed accessors so
 * handlers do not have to repeatedly probe `process.env`.
 */

import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as dotenv from 'dotenv';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

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

export const config = {
  databaseUrl: process.env.DATABASE_URL || 'sqlite://./service.db',
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
};

export default config;
