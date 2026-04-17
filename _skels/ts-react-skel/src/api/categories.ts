/**
 * Typed category repository client.
 *
 * Talks to the wrapper-shared `/api/categories` endpoint. Categories
 * are shared (not per-user) but auth-protected — any authenticated
 * user can CRUD them. Items reference categories via an optional
 * `category_id` FK.
 */

import { config } from '../config';
import { getToken } from '../auth/token-store';
import { AuthError } from './auth';

export interface Category {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface NewCategory {
  name: string;
  description?: string | null;
}

export interface RequestOptions {
  token?: string | null;
  signal?: AbortSignal;
}

const CATEGORIES_BASE = `${config.backendUrl}/api/categories`;

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

export async function listCategories(
  options: RequestOptions = {},
): Promise<Category[]> {
  const response = await fetch(CATEGORIES_BASE, {
    method: 'GET',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  const body = await unwrap<Category[] | { results: Category[] }>(response);
  return Array.isArray(body) ? body : body.results;
}

export async function getCategory(
  id: number,
  options: RequestOptions = {},
): Promise<Category> {
  const response = await fetch(`${CATEGORIES_BASE}/${id}`, {
    method: 'GET',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  return unwrap<Category>(response);
}

export async function createCategory(
  payload: NewCategory,
  options: RequestOptions = {},
): Promise<Category> {
  const response = await fetch(CATEGORIES_BASE, {
    method: 'POST',
    headers: buildHeaders(options, true),
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  return unwrap<Category>(response);
}

export async function updateCategory(
  id: number,
  payload: NewCategory,
  options: RequestOptions = {},
): Promise<Category> {
  const response = await fetch(`${CATEGORIES_BASE}/${id}`, {
    method: 'PUT',
    headers: buildHeaders(options, true),
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  return unwrap<Category>(response);
}

export async function deleteCategory(
  id: number,
  options: RequestOptions = {},
): Promise<void> {
  const response = await fetch(`${CATEGORIES_BASE}/${id}`, {
    method: 'DELETE',
    headers: buildHeaders(options),
    signal: options.signal,
  });
  await unwrap<void>(response);
}
