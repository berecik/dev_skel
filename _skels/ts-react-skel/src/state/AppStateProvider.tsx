/**
 * `AppStateProvider` — top-level Context provider that hydrates the
 * app-state store from the backend on login and clears it on logout.
 *
 * Render this once at the top of `App.tsx` (inside the authenticated
 * branch) and any descendant component can call `useAppState(slice,
 * defaultValue)` to read/write a persisted UI slice.
 *
 * The provider does NOT cache hydration across logins on purpose:
 * each user has their own state, and switching accounts must reset
 * the store cleanly so the new user doesn't see the previous user's
 * preferences.
 */

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactElement,
  type ReactNode,
} from 'react';

import { useAuthToken } from '../auth/use-auth-token';
import { hydrate, reset } from './app-state-store';
import { loadAllState } from './state-api';
import { AuthError } from '../api/items';

interface AppStateContextValue {
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

const AppStateContext = createContext<AppStateContextValue>({
  loading: false,
  error: null,
  reload: async () => {},
});

export function useAppStateContext(): AppStateContextValue {
  return useContext(AppStateContext);
}

export interface AppStateProviderProps {
  children: ReactNode;
}

export default function AppStateProvider({
  children,
}: AppStateProviderProps): ReactElement {
  const { token, isAuthenticated, clearToken } = useAuthToken();

  // Start as loading — the effect below fires immediately on mount.
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Load every state slice from the backend whenever the token
  // changes (login or refresh). On unmount (logout), reset the
  // external store so the next user starts clean.
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    loadAllState({ token, signal: controller.signal })
      .then((snapshot) => {
        if (!cancelled) hydrate(snapshot);
      })
      .catch((err) => {
        if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) {
          return;
        }
        if (err instanceof AuthError) {
          clearToken();
          return;
        }
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
      reset();
    };
  }, [token, clearToken]);

  const reload = async (): Promise<void> => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      const snapshot = await loadAllState({ token });
      hydrate(snapshot);
    } catch (err) {
      if (err instanceof AuthError) {
        clearToken();
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const value = useMemo<AppStateContextValue>(
    () => ({ loading, error, reload }),
    // `reload` is recreated every render but its identity does not
    // need to be stable for descendants — the context value object
    // changes when the visible loading/error state does, which is
    // what consumers actually care about.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [loading, error]
  );

  return (
    <AppStateContext.Provider value={value}>
      {children}
    </AppStateContext.Provider>
  );
}
