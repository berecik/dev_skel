/**
 * `LoginForm` — minimal username/password form that logs into the
 * wrapper-shared `/api/auth/login` endpoint and stores the resulting
 * JWT in the shared token store.
 *
 * Uses `useState` for the controlled inputs and `useCallback` for the
 * submit handler so the closures are stable across renders. The
 * actual HTTP call goes through `loginWithPassword` from the typed
 * item repository module — frontends never talk to fetch directly.
 */

import { useCallback, useState, type FormEvent, type ReactElement } from 'react';

import { AuthError, loginWithPassword } from '../api/items';
import { useAuthToken } from '../auth/use-auth-token';

export interface LoginFormProps {
  /** Optional callback fired right after a successful login. */
  onLoggedIn?: (token: string) => void;
}

export default function LoginForm({ onLoggedIn }: LoginFormProps): ReactElement {
  const { setToken } = useAuthToken();

  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>): Promise<void> => {
      event.preventDefault();
      setSubmitting(true);
      setError(null);
      try {
        const token = await loginWithPassword(username, password);
        setToken(token);
        onLoggedIn?.(token);
      } catch (err) {
        if (err instanceof AuthError) {
          setError('Invalid username or password.');
        } else {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        setSubmitting(false);
      }
    },
    [username, password, setToken, onLoggedIn]
  );

  return (
    <form className="login-form" onSubmit={handleSubmit}>
      <h2>Sign in</h2>

      <label>
        Username
        <input
          type="text"
          name="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          required
        />
      </label>

      <label>
        Password
        <input
          type="password"
          name="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </label>

      <button type="submit" disabled={submitting}>
        {submitting ? 'Signing in…' : 'Sign in'}
      </button>

      {error && <p className="error">{error}</p>}
    </form>
  );
}
