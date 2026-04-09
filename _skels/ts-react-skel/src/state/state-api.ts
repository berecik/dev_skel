/**
 * Typed client for the wrapper-shared `/api/state` endpoints.
 *
 * The default backend (django-bolt) exposes:
 *
 *   GET    /api/state          → returns {key: jsonValue} for the
 *                                 current user (every slice).
 *   PUT    /api/state/<key>    → upserts a single slice; body is
 *                                 `{ "value": "<json string>" }`.
 *   DELETE /api/state/<key>    → drops a single slice.
 *
 * Every request is JWT-protected via the wrapper-shared bearer token
 * (see `src/auth/token-store.ts`). Other backends (django, fastapi,
 * flask, ...) can implement the same contract — see the TODO entry
 * in `TODO.md` and the docs.
 *
 * The `value` payload on the wire is a JSON string so the backend
 * never has to parse it; this module handles the encode/decode for
 * the React side.
 */

import { config } from '../config';
import { AuthError } from '../api/items';
import { getToken } from '../auth/token-store';

export interface RequestOptions {
  token?: string | null;
  signal?: AbortSignal;
}

const STATE_BASE = `${config.backendUrl}/api/state`;

function buildHeaders(options: RequestOptions, json = false): HeadersInit {
  const headers: Record<string, string> = {};
  if (json) {
    headers['Content-Type'] = 'application/json';
  }
  const token = options.token === undefined ? getToken() : options.token;
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function unwrap<T>(response: Response): Promise<T> {
  if (response.status === 401 || response.status === 403) {
    throw new AuthError(`HTTP ${response.status}: authentication required`);
  }
  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`HTTP ${response.status}: ${text || response.statusText}`);
  }
  return (await response.json()) as T;
}

/**
 * Load every state slice for the current user. Returns an object
 * keyed by slice name with already-decoded values.
 *
 * The wire format stores values as JSON strings (so the backend never
 * has to know the shape); this function `JSON.parse`s each one and
 * silently drops slices that fail to parse so a corrupted slice does
 * not block the rest of the cache from loading.
 */
export async function loadAllState(
  options: RequestOptions = {}
): Promise<Record<string, unknown>> {
  const response = await fetch(STATE_BASE, {
    method: 'GET',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  const raw = await unwrap<Record<string, string>>(response);
  const decoded: Record<string, unknown> = {};
  for (const [key, jsonString] of Object.entries(raw)) {
    try {
      decoded[key] = JSON.parse(jsonString);
    } catch {
      // Skip slices that aren't valid JSON — they were probably
      // written by a different version of the app and will be
      // overwritten on the next save.
    }
  }
  return decoded;
}

/**
 * Upsert a single slice. The value is JSON-stringified before being
 * sent so the backend never has to know its shape.
 */
export async function saveState(
  key: string,
  value: unknown,
  options: RequestOptions = {}
): Promise<void> {
  const response = await fetch(`${STATE_BASE}/${encodeURIComponent(key)}`, {
    method: 'PUT',
    headers: buildHeaders(options, true),
    body: JSON.stringify({ value: JSON.stringify(value) }),
    signal: options.signal,
  });
  await unwrap<unknown>(response);
}

/** Drop a single slice. */
export async function deleteState(
  key: string,
  options: RequestOptions = {}
): Promise<void> {
  const response = await fetch(`${STATE_BASE}/${encodeURIComponent(key)}`, {
    method: 'DELETE',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  await unwrap<unknown>(response);
}
