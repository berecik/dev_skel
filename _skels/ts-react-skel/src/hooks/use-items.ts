/**
 * `useItems` — custom React hook that wraps the typed item repository.
 *
 * Demonstrates the canonical react-hooks pattern in dev_skel:
 * - `useState` for local cache + UI status
 * - `useEffect` for data fetching with abort handling
 * - `useCallback` for stable refresh / mutation handlers
 * - `useRef` so the latest token (from `useAuthToken`) is captured by
 *   the long-lived effect closures without re-fetching on every render
 *
 * The hook re-fetches whenever the bearer token changes, so logging in
 * or out re-runs the request without manual wiring in the UI.
 *
 *     const { items, loading, error, refresh, create, complete } = useItems();
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  AuthError,
  type Item,
  type NewItem,
  completeItem as completeItemRequest,
  createItem as createItemRequest,
  listItems as listItemsRequest,
} from '../api/items';
import { useAuthToken } from '../auth/use-auth-token';

export interface UseItemsResult {
  items: Item[];
  loading: boolean;
  error: string | null;
  /** Re-fetch the list explicitly (e.g. after a manual refresh button). */
  refresh: () => Promise<void>;
  /** Create a new item and merge it into the local cache on success. */
  create: (payload: NewItem) => Promise<Item>;
  /** Mark an item complete and replace it in the local cache. */
  complete: (id: number) => Promise<Item>;
  /**
   * `true` when the most recent error was a 401 from the backend —
   * lets the UI render a re-login prompt without sniffing strings.
   */
  unauthorized: boolean;
}

export function useItems(): UseItemsResult {
  const { token, clearToken } = useAuthToken();

  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState<boolean>(false);

  // Capture the freshest token in a ref so the create/complete
  // callbacks always send the right Authorization header even when
  // they were memoised before the latest login.
  const tokenRef = useRef<string | null>(token);
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  // Effect-driven list fetch — re-runs whenever the token changes
  // (login or logout). Abort the in-flight request when the token
  // changes again (or the component unmounts) to avoid setting state
  // on an unmounted hook.
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function load(): Promise<void> {
      setLoading(true);
      setError(null);
      setUnauthorized(false);
      try {
        const data = await listItemsRequest({
          token,
          signal: controller.signal,
        });
        if (!cancelled) {
          setItems(data);
        }
      } catch (err) {
        if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) {
          return;
        }
        if (err instanceof AuthError) {
          setUnauthorized(true);
          // Clear a stale token so the LoginForm shows up immediately.
          clearToken();
          return;
        }
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [token, clearToken]);

  const refresh = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    setUnauthorized(false);
    try {
      const data = await listItemsRequest({ token: tokenRef.current });
      setItems(data);
    } catch (err) {
      if (err instanceof AuthError) {
        setUnauthorized(true);
        clearToken();
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [clearToken]);

  const create = useCallback(
    async (payload: NewItem): Promise<Item> => {
      const created = await createItemRequest(payload, {
        token: tokenRef.current,
      });
      // Optimistic merge into the local cache: prepend so the user
      // sees the new row immediately without waiting for refresh.
      setItems((prev) => [created, ...prev]);
      return created;
    },
    []
  );

  const complete = useCallback(
    async (id: number): Promise<Item> => {
      const updated = await completeItemRequest(id, { token: tokenRef.current });
      setItems((prev) => prev.map((item) => (item.id === id ? updated : item)));
      return updated;
    },
    []
  );

  return {
    items,
    loading,
    error,
    refresh,
    create,
    complete,
    unauthorized,
  };
}
