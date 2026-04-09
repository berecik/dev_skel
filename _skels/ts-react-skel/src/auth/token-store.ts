/**
 * Tiny pub/sub JWT token store.
 *
 * Persists the access token to `localStorage` so refreshes survive a
 * page reload, and notifies subscribers (the `useAuthToken` hook in
 * particular) whenever the token changes. The store falls back to an
 * in-memory value when `localStorage` is unavailable (SSR / sandboxed
 * iframes / unit tests with a fake DOM).
 *
 * The token is intentionally NOT encrypted in storage — production
 * apps should swap this for an httpOnly cookie + a backend session
 * proxy. The skeleton keeps it simple to demonstrate the
 * wrapper-shared JWT secret flow end-to-end.
 */

const STORAGE_KEY = 'devskel.access_token';

type Listener = (token: string | null) => void;

let memoryToken: string | null = null;
const listeners = new Set<Listener>();

function safeStorage(): Storage | null {
  try {
    if (typeof window === 'undefined' || !window.localStorage) {
      return null;
    }
    // Probe the methods we actually use. Node 25+ ships an experimental
    // `localStorage` global as part of `--experimental-webstorage` that
    // can be missing methods (or refuse them when `--localstorage-file`
    // points at an invalid path), and the jsdom <-> node global merge
    // can leave that broken stub in place during vitest runs. Returning
    // `null` here lets the in-memory shim below take over so the
    // wrapper-shared JWT flow keeps working everywhere.
    const storage = window.localStorage;
    if (
      typeof storage.getItem !== 'function' ||
      typeof storage.setItem !== 'function' ||
      typeof storage.removeItem !== 'function'
    ) {
      return null;
    }
    return storage;
  } catch {
    // Some sandboxed environments throw on localStorage access.
  }
  return null;
}

export function getToken(): string | null {
  const storage = safeStorage();
  if (storage) {
    return storage.getItem(STORAGE_KEY);
  }
  return memoryToken;
}

export function setToken(token: string | null): void {
  const storage = safeStorage();
  if (storage) {
    if (token) {
      storage.setItem(STORAGE_KEY, token);
    } else {
      storage.removeItem(STORAGE_KEY);
    }
  } else {
    memoryToken = token;
  }
  for (const listener of listeners) {
    listener(token);
  }
}

export function subscribeToken(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function clearToken(): void {
  setToken(null);
}
