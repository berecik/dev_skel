/**
 * `App` — composes the dev_skel React example.
 *
 * Layout:
 * - Header showing the framework + the wrapper-shared backend URL
 *   and JWT issuer (proves the Vite plugin baked the values from
 *   `<wrapper>/.env` into the bundle).
 * - When the user is not authenticated: the `LoginForm`.
 * - When authenticated: an `<AppStateProvider>` wraps the items UI so
 *   descendants can read/write persistent UI state via `useAppState`.
 *
 * The example demonstrates the canonical react-hooks pattern in
 * dev_skel:
 *   - `useState` for local UI state.
 *   - `useEffect` (inside `useItems`) for data fetching with abort
 *     handling that re-runs whenever the JWT changes.
 *   - `useCallback` to memoise event handlers.
 *   - A custom hook (`useItems`) that wraps the typed item
 *     repository.
 *   - `useAuthToken`, another custom hook, for the wrapper-shared JWT.
 *   - `useAppState('items.showCompleted', true)` (in `ItemList`) for
 *     filter state that persists across reloads via the backend
 *     `/api/state` endpoint — this is the React state management
 *     entry point.
 */

import { type ReactElement } from 'react';

import './App.css';
import { config } from './config';

import LoginForm from './components/LoginForm';
import ItemForm from './components/ItemForm';
import ItemList from './components/ItemList';
import { useAuthToken } from './auth/use-auth-token';
import { useItems } from './hooks/use-items';
import AppStateProvider from './state/AppStateProvider';

function AuthenticatedApp({
  onSignOut,
}: {
  onSignOut: () => void;
}): ReactElement {
  const { items, loading, error, refresh, create, complete } = useItems();

  return (
    <>
      <section className="actions">
        <button type="button" onClick={onSignOut}>
          Sign out
        </button>
      </section>
      <ItemForm create={create} />
      <ItemList
        items={items}
        loading={loading}
        error={error}
        refresh={refresh}
        complete={complete}
      />
    </>
  );
}

function App(): ReactElement {
  const { isAuthenticated, clearToken } = useAuthToken();
  const serviceCount = Object.keys(config.services).length;

  return (
    <div className="app">
      <header className="app-header">
        <h1>dev_skel React</h1>
        <p className="subtitle">
          Wrapper-shared API · React 19 + Vite + TypeScript
        </p>
        <ul className="env-info">
          <li>
            <strong>Backend URL:</strong> <code>{config.backendUrl}</code>
          </li>
          <li>
            <strong>JWT issuer:</strong> <code>{config.jwt.issuer}</code>
          </li>
          <li>
            <strong>Sibling services:</strong> {serviceCount}
          </li>
        </ul>
      </header>

      <main>
        {isAuthenticated ? (
          <AppStateProvider>
            <AuthenticatedApp onSignOut={clearToken} />
          </AppStateProvider>
        ) : (
          <LoginForm />
        )}
      </main>
    </div>
  );
}

export default App;
