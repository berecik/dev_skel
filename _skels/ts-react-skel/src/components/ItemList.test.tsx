/**
 * ItemList — component tests.
 *
 * Verifies list rendering, the persistent "show completed" filter,
 * the complete-button handler, and empty-state messaging. The
 * `useAppState` hook is exercised through the component's real
 * implementation — we prime the in-memory store directly so the
 * hook sees the right initial value without a backend round-trip.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import ItemList from './ItemList';
import { type Item } from '../api/items';
import * as appStateStore from '../state/app-state-store';

const items: Item[] = [
  {
    id: 1,
    name: 'Buy milk',
    description: null,
    is_completed: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Walk the dog',
    description: 'Around the park',
    is_completed: true,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
];

describe('ItemList', () => {
  const mockRefresh = vi.fn();
  const mockComplete = vi.fn();

  beforeEach(() => {
    mockRefresh.mockReset();
    mockComplete.mockReset();
    // Ensure the in-memory state store starts clean.
    appStateStore.reset();
  });

  afterEach(() => {
    cleanup();
    appStateStore.reset();
  });

  it('renders all items when showCompleted is true', () => {
    // Prime the store so useAppState('items.showCompleted', true)
    // reads true from the in-memory snapshot.
    appStateStore.setSlice('items.showCompleted', true);

    render(
      <ItemList
        items={items}
        loading={false}
        error={null}
        refresh={mockRefresh}
        complete={mockComplete}
      />,
    );

    expect(screen.getByText('Buy milk')).toBeInTheDocument();
    expect(screen.getByText('Walk the dog')).toBeInTheDocument();
  });

  it('hides completed items when showCompleted is false', () => {
    appStateStore.setSlice('items.showCompleted', false);

    render(
      <ItemList
        items={items}
        loading={false}
        error={null}
        refresh={mockRefresh}
        complete={mockComplete}
      />,
    );

    expect(screen.getByText('Buy milk')).toBeInTheDocument();
    expect(screen.queryByText('Walk the dog')).not.toBeInTheDocument();
  });

  it('shows "Mark complete" button for incomplete items only', () => {
    appStateStore.setSlice('items.showCompleted', true);

    render(
      <ItemList
        items={items}
        loading={false}
        error={null}
        refresh={mockRefresh}
        complete={mockComplete}
      />,
    );

    // "Buy milk" (incomplete) should have a Mark complete button.
    const buttons = screen.getAllByRole('button', { name: /mark complete/i });
    expect(buttons).toHaveLength(1);
  });

  it('calls complete handler when Mark complete is clicked', () => {
    appStateStore.setSlice('items.showCompleted', true);
    mockComplete.mockResolvedValueOnce({ ...items[0], is_completed: true });

    render(
      <ItemList
        items={items}
        loading={false}
        error={null}
        refresh={mockRefresh}
        complete={mockComplete}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /mark complete/i }));
    expect(mockComplete).toHaveBeenCalledWith(1); // item id=1
  });

  it('shows empty message when no items exist', () => {
    render(
      <ItemList
        items={[]}
        loading={false}
        error={null}
        refresh={mockRefresh}
        complete={mockComplete}
      />,
    );

    expect(screen.getByText(/no items yet/i)).toBeInTheDocument();
  });

  it('shows error message when error is present', () => {
    render(
      <ItemList
        items={[]}
        loading={false}
        error="something broke"
        refresh={mockRefresh}
        complete={mockComplete}
      />,
    );

    expect(screen.getByText(/something broke/i)).toBeInTheDocument();
  });
});
