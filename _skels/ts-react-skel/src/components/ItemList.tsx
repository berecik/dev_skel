/**
 * `ItemList` — renders the items returned by the `useItems` hook with
 * a "complete" button that flips `is_completed` on the row in place,
 * plus a "show completed" filter that **persists across reloads** via
 * the wrapper-shared `/api/state` endpoint.
 *
 * The filter state is the dev_skel canonical demo of the React state
 * management layer:
 *
 *   const [showCompleted, setShowCompleted] = useAppState<boolean>(
 *     'items.showCompleted',
 *     true,
 *   );
 *
 * The hook reads/writes the slice through `src/state/use-app-state.ts`,
 * which auto-saves to the backend `/api/state/<key>` endpoint on every
 * `setShowCompleted` call. The `AppStateProvider` mounted in
 * `App.tsx` hydrates the initial value from the backend on login, so
 * the very first render after a refresh has the right value with no
 * waterfall fetch.
 *
 * Receives the resolved `useItems` hook fields from the parent so the
 * parent can share a single cache with `<ItemForm />`.
 */

import { useCallback, useMemo, type ReactElement } from 'react';

import { type Item } from '../api/items';
import { type Category } from '../api/categories';
import { useAppState } from '../state/use-app-state';

export interface ItemListProps {
  items: Item[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  complete: (id: number) => Promise<Item>;
  categories?: Category[];
}

export default function ItemList({
  items,
  loading,
  error,
  refresh,
  complete,
  categories = [],
}: ItemListProps): ReactElement {
  const categoryMap = useMemo(
    () => new Map(categories.map((c) => [c.id, c.name])),
    [categories],
  );
  // Persistent UI filter — shared across browser reloads via the
  // backend `/api/state` endpoint.
  const [showCompleted, setShowCompleted] = useAppState<boolean>(
    'items.showCompleted',
    true
  );

  const visibleItems = useMemo(
    () => (showCompleted ? items : items.filter((item) => !item.is_completed)),
    [items, showCompleted]
  );

  const handleComplete = useCallback(
    async (id: number): Promise<void> => {
      try {
        await complete(id);
      } catch {
        // Errors surface via the parent hook's `error` field on the
        // next render — we just swallow them here so a failing button
        // press does not blow up the rest of the list.
      }
    },
    [complete]
  );

  if (loading && items.length === 0) {
    return <p className="status">Loading items…</p>;
  }

  return (
    <section className="item-list">
      <header>
        <h2>
          Items ({visibleItems.length}
          {visibleItems.length !== items.length ? ` of ${items.length}` : ''})
        </h2>
        <div className="item-list-actions">
          <label className="filter-toggle">
            <input
              type="checkbox"
              checked={showCompleted}
              onChange={(event) => setShowCompleted(event.target.checked)}
            />
            Show completed
          </label>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
          >
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </header>

      {error && <p className="error">Error: {error}</p>}

      {visibleItems.length === 0 ? (
        <p className="empty">
          {items.length === 0
            ? 'No items yet — create one above.'
            : 'No items match the current filter.'}
        </p>
      ) : (
        <ul>
          {visibleItems.map((item) => (
            <li
              key={item.id}
              className={item.is_completed ? 'item done' : 'item'}
            >
              <div className="item-body">
                <strong>{item.name}</strong>
                {item.description && <p>{item.description}</p>}
                {item.category_id && categoryMap.has(item.category_id) && (
                  <span className="category-badge">{categoryMap.get(item.category_id)}</span>
                )}
                <small>updated {item.updated_at}</small>
              </div>
              {!item.is_completed && (
                <button
                  type="button"
                  onClick={() => void handleComplete(item.id)}
                >
                  Mark complete
                </button>
              )}
              {item.is_completed && <span className="badge">✓ done</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
