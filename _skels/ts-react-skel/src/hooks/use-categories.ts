/**
 * `useCategories` — custom React hook that wraps the categories client.
 *
 * Same pattern as `useItems`: re-fetches when the bearer token changes,
 * provides `create` / `refresh` callbacks, and surfaces `unauthorized`
 * so the UI can prompt for login.
 *
 *     const { categories, loading, error, refresh, create } = useCategories();
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuthToken } from '../auth/use-auth-token';
import {
  type Category,
  type NewCategory,
  listCategories,
  createCategory,
} from '../api/categories';
import { AuthError } from '../api/auth';

export interface UseCategoriesResult {
  categories: Category[];
  loading: boolean;
  error: string | null;
  unauthorized: boolean;
  refresh: () => void;
  create: (payload: NewCategory) => Promise<Category | null>;
}

export function useCategories(): UseCategoriesResult {
  const { token } = useAuthToken();
  const tokenRef = useRef(token);
  useEffect(() => { tokenRef.current = token; }, [token]);

  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  useEffect(() => {
    if (!tokenRef.current) {
      setCategories([]);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    listCategories({ token: tokenRef.current, signal: controller.signal })
      .then((data) => {
        setCategories(data);
        setUnauthorized(false);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        if (err instanceof AuthError) {
          setUnauthorized(true);
        }
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [token, refreshKey]);

  const create = useCallback(
    async (payload: NewCategory): Promise<Category | null> => {
      try {
        const cat = await createCategory(payload, {
          token: tokenRef.current,
        });
        setCategories((prev) => [...prev, cat]);
        return cat;
      } catch (err) {
        if (err instanceof AuthError) setUnauthorized(true);
        setError(err instanceof Error ? err.message : String(err));
        return null;
      }
    },
    [],
  );

  return { categories, loading, error, unauthorized, refresh, create };
}
