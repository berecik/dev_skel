/**
 * Typed order workflow client.
 *
 * Talks to the wrapper-shared `/api/catalog` and `/api/orders`
 * endpoints exposed by the default backend. The base URL comes from
 * `config.backendUrl`, which the Vite plugin bakes in from
 * `<wrapper>/.env`'s `BACKEND_URL`.
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

// ── Types ───────────────────────────────────────────────────────────

export interface CatalogItem {
  id: number;
  name: string;
  description: string;
  price: number;
  category: string;
  available: boolean;
}

export interface OrderLine {
  id: number;
  catalog_item_id: number;
  quantity: number;
  unit_price: number;
}

export interface OrderAddress {
  id: number;
  street: string;
  city: string;
  zip_code: string;
  phone: string;
  notes: string;
}

export interface Order {
  id: number;
  user_id: number;
  status: string;
  created_at: string;
  submitted_at?: string;
  wait_minutes?: number;
  feedback?: string;
}

export interface OrderDetail extends Order {
  lines: OrderLine[];
  address: OrderAddress | null;
}

export interface NewCatalogItem {
  name: string;
  description?: string;
  price: number;
  category?: string;
  available?: boolean;
}

export interface NewOrderLine {
  catalog_item_id: number;
  quantity: number;
}

export interface NewOrderAddress {
  street: string;
  city: string;
  zip_code: string;
  phone: string;
  notes?: string;
}

export interface ApproveBody {
  wait_minutes: number;
  feedback: string;
}

export interface RejectBody {
  feedback: string;
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

// ── Internals ───────────────────────────────────────────────────────

const CATALOG_BASE = `${config.backendUrl}/api/catalog`;
const ORDERS_BASE = `${config.backendUrl}/api/orders`;

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
  if (response.status === 204) {
    return undefined as unknown as T;
  }
  return (await response.json()) as T;
}

// ── Catalog ─────────────────────────────────────────────────────────

export async function listCatalog(
  options: RequestOptions = {},
): Promise<CatalogItem[]> {
  const response = await fetch(CATALOG_BASE, {
    method: 'GET',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  const body = await unwrap<CatalogItem[] | { results?: CatalogItem[]; items?: CatalogItem[] }>(response);
  if (Array.isArray(body)) return body;
  return body.results ?? body.items ?? [];
}

export async function createCatalogItem(
  payload: NewCatalogItem,
  options: RequestOptions = {},
): Promise<CatalogItem> {
  const response = await fetch(CATALOG_BASE, {
    method: 'POST',
    headers: buildHeaders(options, true),
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  return unwrap<CatalogItem>(response);
}

// ── Orders ──────────────────────────────────────────────────────────

export async function createOrder(
  options: RequestOptions = {},
): Promise<Order> {
  const response = await fetch(ORDERS_BASE, {
    method: 'POST',
    headers: buildHeaders(options, true),
    body: JSON.stringify({}),
    signal: options.signal,
  });
  return unwrap<Order>(response);
}

export async function listOrders(
  options: RequestOptions = {},
): Promise<Order[]> {
  const response = await fetch(ORDERS_BASE, {
    method: 'GET',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  const body = await unwrap<Order[] | { results?: Order[]; items?: Order[] }>(response);
  if (Array.isArray(body)) return body;
  return body.results ?? body.items ?? [];
}

export async function getOrder(
  id: number,
  options: RequestOptions = {},
): Promise<OrderDetail> {
  const response = await fetch(`${ORDERS_BASE}/${id}`, {
    method: 'GET',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  return unwrap<OrderDetail>(response);
}

export async function addOrderLine(
  orderId: number,
  payload: NewOrderLine,
  options: RequestOptions = {},
): Promise<OrderLine> {
  const response = await fetch(`${ORDERS_BASE}/${orderId}/lines`, {
    method: 'POST',
    headers: buildHeaders(options, true),
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  return unwrap<OrderLine>(response);
}

export async function removeOrderLine(
  orderId: number,
  lineId: number,
  options: RequestOptions = {},
): Promise<void> {
  const response = await fetch(`${ORDERS_BASE}/${orderId}/lines/${lineId}`, {
    method: 'DELETE',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  await unwrap<void>(response);
}

export async function setOrderAddress(
  orderId: number,
  payload: NewOrderAddress,
  options: RequestOptions = {},
): Promise<void> {
  const response = await fetch(`${ORDERS_BASE}/${orderId}/address`, {
    method: 'PUT',
    headers: buildHeaders(options, true),
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  await unwrap<void>(response);
}

export async function submitOrder(
  orderId: number,
  options: RequestOptions = {},
): Promise<Order> {
  const response = await fetch(`${ORDERS_BASE}/${orderId}/submit`, {
    method: 'POST',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  return unwrap<Order>(response);
}

export async function approveOrder(
  orderId: number,
  payload: ApproveBody,
  options: RequestOptions = {},
): Promise<Order> {
  const response = await fetch(`${ORDERS_BASE}/${orderId}/approve`, {
    method: 'POST',
    headers: buildHeaders(options, true),
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  return unwrap<Order>(response);
}

export async function rejectOrder(
  orderId: number,
  payload: RejectBody,
  options: RequestOptions = {},
): Promise<Order> {
  const response = await fetch(`${ORDERS_BASE}/${orderId}/reject`, {
    method: 'POST',
    headers: buildHeaders(options, true),
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  return unwrap<Order>(response);
}
