/**
 * `useAppState` — React hook bridging the app-state pub/sub store
 * with React's render cycle, plus optional auto-save to the wrapper-shared
 * `/api/state` endpoint.
 *
 *     const [showCompleted, setShowCompleted] = useAppState<boolean>(
 *       'items.showCompleted',
 *       true,
 *     );
 *
 * Behaves like `useState` for callers — but every `setShowCompleted`
 * call:
 *   1. Updates the in-memory store (so other components observing the
 *      same slice re-render immediately).
 *   2. Fires off `saveState(...)` against the backend so the value
 *      persists across page reloads.
 *
 * Reads use the in-memory store as the source of truth (the
 * `AppStateProvider` hydrates it on login from the backend), so the
 * very first render after a refresh has the right value with no
 * waterfall of `useEffect` data fetches.
 */

import { useCallback, useEffect, useState } from 'react';

import {
  getSlice,
  setSlice,
  subscribeSlice,
} from './app-state-store';
import { saveState } from './state-api';

export type SetState<T> = (next: T | ((prev: T) => T)) => void;

interface UseAppStateOptions {
  /**
   * When false, mutations only update the in-memory store and don't
   * call the backend. Useful for transient state that should not be
   * persisted (e.g. an in-progress draft).
   */
  persist?: boolean;
}

export function useAppState<T>(
  key: string,
  defaultValue: T,
  options: UseAppStateOptions = {}
): [T, SetState<T>] {
  const persist = options.persist ?? true;

  // Initial value: pull from the in-memory store first (it may already
  // contain a hydrated value from `AppStateProvider`); otherwise fall
  // back to the caller-supplied default.
  const [value, setLocalValue] = useState<T>(() => {
    const existing = getSlice<T>(key);
    return existing === undefined ? defaultValue : existing;
  });

  // Subscribe to cross-component changes so other consumers writing
  // the same slice re-render this component too.
  useEffect(() => {
    return subscribeSlice<T>(key, (next) => {
      setLocalValue(next === undefined ? defaultValue : next);
    });
    // We deliberately omit `defaultValue` from the dep list — its
    // identity is allowed to change without triggering a re-subscribe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const setValue = useCallback<SetState<T>>(
    (next) => {
      const previous =
        getSlice<T>(key) === undefined ? defaultValue : (getSlice<T>(key) as T);
      const resolved =
        typeof next === 'function'
          ? (next as (prev: T) => T)(previous)
          : next;

      setSlice(key, resolved);

      if (persist) {
        // Fire-and-forget save. We swallow errors here because the
        // store has already updated locally — production apps should
        // surface a toast / retry queue, but the skeleton keeps it
        // minimal.
        void saveState(key, resolved).catch(() => {
          /* swallowed — see comment above */
        });
      }
    },
    [key, persist, defaultValue]
  );

  return [value, setValue];
}
