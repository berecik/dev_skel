/**
 * App-state pub/sub store.
 *
 * Holds arbitrary JSON-serialisable slices of state keyed by string
 * (e.g. `"items.showCompleted"`, `"sidebar.collapsed"`). Subscribers
 * are notified whenever a slice changes — the React side wires this
 * up via `useAppState` so any component reading a slice re-renders
 * automatically when another component (or the loader) writes a new
 * value.
 *
 * The store is intentionally framework-agnostic and dependency-free.
 * The persistence layer (writing to the backend `/api/state` endpoint)
 * lives in `state-api.ts` + `AppStateProvider.tsx` so the store
 * itself stays simple and unit-testable.
 */

export type StateValue = unknown;
export type StateMap = Record<string, StateValue>;

type Listener<T = StateValue> = (next: T | undefined) => void;

const data: StateMap = {};
const listeners = new Map<string, Set<Listener>>();
const globalListeners = new Set<(snapshot: StateMap) => void>();

export function getSlice<T = StateValue>(key: string): T | undefined {
  return data[key] as T | undefined;
}

export function setSlice<T = StateValue>(key: string, value: T): void {
  data[key] = value;
  const subs = listeners.get(key);
  if (subs) {
    for (const listener of subs) {
      listener(value);
    }
  }
  const snapshot = { ...data };
  for (const listener of globalListeners) {
    listener(snapshot);
  }
}

export function deleteSlice(key: string): void {
  delete data[key];
  const subs = listeners.get(key);
  if (subs) {
    for (const listener of subs) {
      listener(undefined);
    }
  }
  const snapshot = { ...data };
  for (const listener of globalListeners) {
    listener(snapshot);
  }
}

export function subscribeSlice<T = StateValue>(
  key: string,
  listener: Listener<T>
): () => void {
  let subs = listeners.get(key);
  if (!subs) {
    subs = new Set();
    listeners.set(key, subs);
  }
  subs.add(listener as Listener);
  return () => {
    subs!.delete(listener as Listener);
  };
}

export function subscribeAll(
  listener: (snapshot: StateMap) => void
): () => void {
  globalListeners.add(listener);
  return () => {
    globalListeners.delete(listener);
  };
}

/**
 * Replace the entire store with a fresh snapshot. Used by the
 * `AppStateProvider` to hydrate from the backend on login. Notifies
 * every listener exactly once with the value relevant to its slice.
 */
export function hydrate(snapshot: StateMap): void {
  // Diff against current contents so listeners only fire when something
  // actually changed.
  const allKeys = new Set([...Object.keys(data), ...Object.keys(snapshot)]);
  for (const key of allKeys) {
    if (snapshot[key] === undefined) {
      delete data[key];
    } else {
      data[key] = snapshot[key];
    }
    const subs = listeners.get(key);
    if (subs) {
      for (const listener of subs) {
        listener(snapshot[key]);
      }
    }
  }
  const finalSnapshot = { ...data };
  for (const listener of globalListeners) {
    listener(finalSnapshot);
  }
}

/**
 * Drop every slice. Called by `AppStateProvider` when the user logs
 * out so the next login starts from a clean slate.
 */
export function reset(): void {
  hydrate({});
}

export function snapshot(): StateMap {
  return { ...data };
}
