/**
 * ItemForm — component tests.
 *
 * Verifies form rendering, controlled inputs, submission callback,
 * form reset after success, and error display. The `create` prop is
 * a mock function — no real backend needed.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import ItemForm from './ItemForm';
import { AuthError, type Item } from '../api/items';

const fakeItem: Item = {
  id: 42,
  name: 'Test item',
  description: 'desc',
  is_completed: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('ItemForm', () => {
  let mockCreate: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockCreate = vi.fn();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders name + description fields and a submit button', () => {
    render(<ItemForm create={mockCreate} />);
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create item/i })).toBeInTheDocument();
  });

  it('calls create callback and clears inputs on success', async () => {
    mockCreate.mockResolvedValueOnce(fakeItem);

    render(<ItemForm create={mockCreate} />);
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'New thing' } });
    fireEvent.change(screen.getByLabelText(/description/i), { target: { value: 'Details' } });
    fireEvent.click(screen.getByRole('button', { name: /create item/i }));

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith({
        name: 'New thing',
        description: 'Details',
      });
    });

    // After a successful create, both fields should be cleared.
    await waitFor(() => {
      expect((screen.getByLabelText(/name/i) as HTMLInputElement).value).toBe('');
      expect((screen.getByLabelText(/description/i) as HTMLTextAreaElement).value).toBe('');
    });
  });

  it('shows "session expired" on AuthError', async () => {
    mockCreate.mockRejectedValueOnce(new AuthError('Unauthorized'));

    render(<ItemForm create={mockCreate} />);
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'x' } });
    fireEvent.click(screen.getByRole('button', { name: /create item/i }));

    await waitFor(() => {
      expect(screen.getByText(/session expired/i)).toBeInTheDocument();
    });
  });

  it('disables submit when name is empty', () => {
    render(<ItemForm create={mockCreate} />);
    const btn = screen.getByRole('button', { name: /create item/i });
    expect(btn).toBeDisabled();
  });
});
