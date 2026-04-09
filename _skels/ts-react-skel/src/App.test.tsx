/**
 * `App` smoke tests.
 *
 * Each test resets the wrapper-shared token store via the token store's
 * own `clearToken()` API in `beforeEach` so the auth state does not
 * leak between cases. We deliberately do NOT poke at
 * `window.localStorage.clear()` directly: Node 25+ ships an
 * experimental `localStorage` global that lacks methods and conflicts
 * with jsdom's implementation, so reaching into `window.localStorage`
 * is non-portable. The token store's `clearToken()` already calls
 * `removeItem` (or falls back to its in-memory shim) safely on every
 * test environment.
 *
 * The tests intentionally do not stub `fetch` — the unauthenticated
 * case never makes a network call (the LoginForm is rendered first),
 * and the authenticated case is exercised by the dev_skel
 * `_bin/test-react-django-bolt-integration` runner end-to-end.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import App from './App';
import { clearToken } from './auth/token-store';

describe('App', () => {
  beforeEach(() => {
    clearToken();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    render(<App />);
    expect(document.body).toBeInTheDocument();
  });

  it('renders the framework banner from the wrapper-shared config', () => {
    render(<App />);
    expect(screen.getByText('dev_skel React')).toBeInTheDocument();
    expect(screen.getByText(/React 19/)).toBeInTheDocument();
  });

  it('shows the LoginForm when there is no stored JWT', () => {
    render(<App />);
    expect(
      screen.getByRole('heading', { name: /sign in/i })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /sign in/i })
    ).toBeInTheDocument();
  });
});
