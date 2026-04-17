/**
 * Typed item repository client.
 *
 * Talks to the wrapper-shared `/api/items` endpoint exposed by the
 * default backend (django-bolt out of the box, but every dev_skel
 * backend can serve the same contract — see
 * `_docs/SHARED-DATABASE-CONVENTIONS.md`). The base URL comes from
 * `config.backendUrl`, which the Vite plugin bakes in from
 * `<wrapper>/.env`'s `BACKEND_URL` (see `vite.config.ts` and
 * `src/config.ts`).
 *
 * Authentication: every request automatically attaches an
 * `Authorization: Bearer <token>` header when a token is present in
 * the wrapper-shared store (`src/auth/token-store.ts`). Pass an
 * explicit token via the `token` option to override the stored value.
 *
 * The client throws `AuthError` on 401 responses so the UI can show a
 * login form, and a generic `Error` on every other non-2xx status.
 */

import { config } from '../config';
import { getToken } from '../auth/token-store';
import { AuthError } from './auth';

export { AuthError } from './auth';
export { loginWithPassword } from './auth';

export interface Item {
  id: number;
  name: string;
  description: string | null;
  is_completed: boolean;
  category_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface NewItem {
  name: string;
  description?: string | null;
  is_completed?: boolean;
  category_id?: number | null;
}

export interface RequestOptions {
  /**
   * Override the bearer token for this request only. Useful in tests
   * and in the login flow (where the new token isn't in the store yet
   * when the very first authenticated call goes out).
   */
  token?: string | null;
  /** Abort signal forwarded to `fetch`. */
  signal?: AbortSignal;
}

const ITEMS_BASE = `${config.backendUrl}/api/items`;

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

export async function listItems(options: RequestOptions = {}): Promise<Item[]> {
  const response = await fetch(ITEMS_BASE, {
    method: 'GET',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  return unwrap<Item[]>(response);
}

export async function getItem(
  id: number,
  options: RequestOptions = {}
): Promise<Item> {
  const response = await fetch(`${ITEMS_BASE}/${id}`, {
    method: 'GET',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  return unwrap<Item>(response);
}

export async function createItem(
  payload: NewItem,
  options: RequestOptions = {}
): Promise<Item> {
  const response = await fetch(ITEMS_BASE, {
    method: 'POST',
    headers: buildHeaders(options, true),
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  return unwrap<Item>(response);
}

export async function completeItem(
  id: number,
  options: RequestOptions = {}
): Promise<Item> {
  const response = await fetch(`${ITEMS_BASE}/${id}/complete`, {
    method: 'POST',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  return unwrap<Item>(response);
}

