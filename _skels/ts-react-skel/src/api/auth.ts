/**
 * Authentication helpers.
 *
 * Provides the shared `AuthError` class (thrown on 401/403 responses
 * throughout the app) and `loginWithPassword` (the canonical login
 * flow against the wrapper-shared `/api/auth/login` endpoint).
 *
 * Every API module that needs to distinguish auth failures from
 * network errors should import `AuthError` from here rather than
 * defining its own.
 */

import { config } from '../config';

/**
 * 401 / 403 responses get their own error class so the UI can render
 * a login form instead of an error banner.
 */
export class AuthError extends Error {
  constructor(message = 'Authentication required') {
    super(message);
    this.name = 'AuthError';
  }
}

export interface RequestOptions {
  /** Abort signal forwarded to `fetch`. */
  signal?: AbortSignal;
}

/**
 * Login helper — POSTs username/password to the wrapper-shared
 * `/api/auth/login` endpoint and returns the access token.
 *
 * The endpoint shape matches the canonical dev_skel backend response
 * (`{ access, refresh, user_id, username }`); we ignore the refresh
 * token for now to keep the example minimal.
 */
export async function loginWithPassword(
  username: string,
  password: string,
  options: RequestOptions = {}
): Promise<string> {
  const response = await fetch(`${config.backendUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
    signal: options.signal,
  });
  if (response.status === 401) {
    throw new AuthError('Invalid credentials');
  }
  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`HTTP ${response.status}: ${text || response.statusText}`);
  }
  const body = (await response.json()) as { access?: string; token?: string };
  const token = body.access ?? body.token;
  if (!token) {
    throw new Error('Login response did not include an access token');
  }
  return token;
}
