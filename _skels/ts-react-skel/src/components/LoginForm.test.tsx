/**
 * LoginForm — component tests.
 *
 * Verifies form rendering, submission with `loginWithPassword`,
 * token-store integration, and error display paths. Uses a stubbed
 * `loginWithPassword` (vi.mock) so no real backend is needed.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import LoginForm from './LoginForm';
import { clearToken, getToken } from '../auth/token-store';

// Mock the items module so loginWithPassword is controllable.
vi.mock('../api/items', async () => {
  const actual = await vi.importActual<typeof import('../api/items')>('../api/items');
  return {
    ...actual,
    loginWithPassword: vi.fn(),
  };
});

import { AuthError, loginWithPassword } from '../api/items';

const mockLogin = vi.mocked(loginWithPassword);

describe('LoginForm', () => {
  beforeEach(() => {
    clearToken();
    mockLogin.mockReset();
  });

  afterEach(() => {
    cleanup();
    clearToken();
  });

  it('renders username + password fields and a submit button', () => {
    render(<LoginForm />);
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('calls loginWithPassword and stores the token on success', async () => {
    mockLogin.mockResolvedValueOnce('fake-jwt-token');

    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'alice' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pass' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('alice', 'pass');
    });
    // The token should now be in the store.
    await waitFor(() => {
      expect(getToken()).toBe('fake-jwt-token');
    });
  });

  it('displays "Invalid username or password" on AuthError', async () => {
    mockLogin.mockRejectedValueOnce(new AuthError('bad creds'));

    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'alice' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid username or password/i)).toBeInTheDocument();
    });
    expect(getToken()).toBeNull();
  });

  it('displays generic error message on network failure', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Network unreachable'));

    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'alice' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pass' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/network unreachable/i)).toBeInTheDocument();
    });
  });
});
