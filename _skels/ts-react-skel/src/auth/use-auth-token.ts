/**
 * `useAuthToken` — React hook for the wrapper-shared JWT bearer token.
 *
 * Re-renders the component whenever `setToken` is called from anywhere
 * in the app, and exposes a small API:
 *
 *   const { token, setToken, clearToken, isAuthenticated } = useAuthToken();
 *
 * The underlying store persists to `localStorage` (see
 * `./token-store.ts`) so a refresh keeps the user logged in.
 */

import { useCallback, useEffect, useState } from 'react';

import {
  clearToken as clearTokenStore,
  getToken,
  setToken as setTokenStore,
  subscribeToken,
} from './token-store';

export interface UseAuthToken {
  token: string | null;
  isAuthenticated: boolean;
  setToken: (token: string | null) => void;
  clearToken: () => void;
}

export function useAuthToken(): UseAuthToken {
  const [token, setLocalToken] = useState<string | null>(() => getToken());

  // Subscribe to cross-component token changes so a login in one
  // component refreshes any other component that displays the token.
  useEffect(() => {
    return subscribeToken((next) => {
      setLocalToken(next);
    });
  }, []);

  const setToken = useCallback((next: string | null) => {
    setTokenStore(next);
  }, []);

  const clearToken = useCallback(() => {
    clearTokenStore();
  }, []);

  return {
    token,
    isAuthenticated: Boolean(token),
    setToken,
    clearToken,
  };
}
