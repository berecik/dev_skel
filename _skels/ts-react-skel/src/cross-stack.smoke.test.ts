/**
 * Cross-stack smoke test — exercises the REAL `src/api/items.ts`
 * client against a live backend.
 *
 * This is the test the dev_skel `_bin/test-react-*-integration` runners
 * launch AFTER they have generated the wrapper, rebuilt the React
 * bundle (so `import.meta.env.VITE_BACKEND_URL` reflects the rewritten
 * port), started the backend, and confirmed the backend serves the
 * canonical items contract via a Python HTTP pre-flight.
 *
 * The runners enable this test by setting two environment variables:
 *
 *   RUN_CROSS_STACK_SMOKE=1   — gate (every other vitest run skips)
 *   BACKEND_URL=http://...    — used for the register pre-step (which
 *                                items.ts has no helper for)
 *
 * Without those vars the entire suite no-ops, so a developer running
 * `npm test` against a fresh wrapper sees nothing surprising.
 *
 * The filename intentionally does NOT contain the `.test.` infix that
 * vitest's default glob looks for, so `npm test` ignores it. The
 * cross-stack runner invokes vitest with this file path explicitly:
 *
 *     RUN_CROSS_STACK_SMOKE=1 BACKEND_URL=http://127.0.0.1:18765 \
 *         npx vitest run src/cross-stack.smoke.ts
 *
 * Why we run this through vitest instead of a Python HTTP exercise:
 * the Python pre-flight only proves the *backend* serves the contract.
 * This test additionally proves the *frontend's own client code* knows
 * how to talk to the backend — same `loginWithPassword` parsing, same
 * `Authorization: Bearer` header injection, same `AuthError` thrown on
 * 401, same response-shape handling. A regression in `src/api/items.ts`
 * would surface here long before a real user opens the app.
 */

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import {
  AuthError,
  type Item,
  type NewItem,
  completeItem,
  createItem,
  getItem,
  listItems,
  loginWithPassword,
} from './api/items';
import { clearToken, getToken, setToken } from './auth/token-store';
import { config } from './config';
import { deleteState, loadAllState, saveState } from './state/state-api';

const RUN_SMOKE = process.env.RUN_CROSS_STACK_SMOKE === '1';
const SMOKE_USERNAME =
  process.env.SMOKE_USERNAME ?? 'react-smoke-user';
const SMOKE_PASSWORD =
  process.env.SMOKE_PASSWORD ?? 'react-smoke-pw-12345';
const SMOKE_EMAIL =
  process.env.SMOKE_EMAIL ?? 'react-smoke@example.com';
const SMOKE_ITEM_NAME =
  process.env.SMOKE_ITEM_NAME ?? 'react-smoke-test-item';
const SMOKE_ITEM_DESCRIPTION =
  'Created by the React frontend cross-stack smoke test';

/**
 * Tiny helper for the one endpoint the React items.ts client doesn't
 * cover: `/api/auth/register`. Mirrors what `_react_backend_lib`'s
 * Python pre-flight does so the smoke can stand up its own user.
 *
 * The `react-smoke-user` username is intentionally distinct from the
 * Python pre-flight's `react-integration-user` so the two flows do
 * NOT collide on backends that allow concurrent users (which is
 * every backend that ships the wrapper-shared register endpoint).
 */
async function registerSmokeUser(): Promise<number> {
  const response = await fetch(`${config.backendUrl}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: SMOKE_USERNAME,
      email: SMOKE_EMAIL,
      password: SMOKE_PASSWORD,
      password_confirm: SMOKE_PASSWORD,
    }),
  });
  if (response.status !== 201) {
    const text = await response.text().catch(() => '');
    throw new Error(
      `register expected 201, got ${response.status}: ${text}`,
    );
  }
  const body = (await response.json()) as { user?: { id?: number } };
  const id = body.user?.id;
  if (!id) {
    throw new Error(
      `register response missing user.id: ${JSON.stringify(body)}`,
    );
  }
  return id;
}

describe.skipIf(!RUN_SMOKE)(
  'cross-stack smoke (real items.ts → live backend)',
  () => {
    beforeAll(() => {
      // The smoke test owns the token store for its duration. Reset
      // before we start so a stale value from another test cannot
      // bleed in.
      clearToken();
    });

    afterAll(() => {
      clearToken();
    });

    it(
      'round-trips through every items.ts function against the live backend',
      async () => {
        // Sanity: the Vite plugin should have baked the rewritten
        // BACKEND_URL into config.backendUrl by the time we get here.
        expect(config.backendUrl).toMatch(/^https?:\/\//);
        // The runner exports BACKEND_URL too — they should agree.
        if (process.env.BACKEND_URL) {
          expect(config.backendUrl).toBe(process.env.BACKEND_URL);
        }

        // Sub-step 1: register (the only step that uses raw fetch — no
        // helper in items.ts). Smoke uses its own user so it never
        // conflicts with the Python pre-flight's user.
        const userId = await registerSmokeUser();
        expect(userId).toBeGreaterThan(0);

        // Sub-step 2: login → JWT via the REAL items.ts helper. This
        // exercises both the `{access}` and `{token}` response shapes
        // that `loginWithPassword` tolerates.
        const token = await loginWithPassword(SMOKE_USERNAME, SMOKE_PASSWORD);
        expect(typeof token).toBe('string');
        expect(token.length).toBeGreaterThan(20);

        // Stash the token in the wrapper-shared store so subsequent
        // calls auto-attach the Bearer header (the production code
        // path the React UI takes after a successful login).
        setToken(token);
        expect(getToken()).toBe(token);

        // Sub-step 3: list items (initial). We don't assert on the
        // count because some backends share items across users — the
        // post-create assertion below checks that the count GREW by 1,
        // which is robust to either schema.
        const initial = await listItems();
        expect(Array.isArray(initial)).toBe(true);
        const initialCount = initial.length;

        // Sub-step 4: create an item via the REAL helper. This
        // exercises buildHeaders + JSON serialisation + the 201 unwrap.
        const payload: NewItem = {
          name: SMOKE_ITEM_NAME,
          description: SMOKE_ITEM_DESCRIPTION,
          is_completed: false,
        };
        const created: Item = await createItem(payload);
        expect(created.id).toBeGreaterThan(0);
        expect(created.name).toBe(SMOKE_ITEM_NAME);
        expect(created.is_completed).toBe(false);

        // Sub-step 5: list again — the new item must be visible.
        const after = await listItems();
        expect(after.length).toBe(initialCount + 1);
        const names = after.map((item) => item.name);
        expect(names).toContain(SMOKE_ITEM_NAME);

        // Sub-step 6: round-trip the item via getItem (exercises the
        // path-parameter helper).
        const fetched = await getItem(created.id);
        expect(fetched.id).toBe(created.id);
        expect(fetched.name).toBe(SMOKE_ITEM_NAME);

        // Sub-step 7: complete via the @action endpoint. The response
        // body must reflect the new is_completed=true state.
        const completed = await completeItem(created.id);
        expect(completed.id).toBe(created.id);
        expect(completed.is_completed).toBe(true);

        // Sub-step 8: state API — save, load, delete roundtrip.
        // This exercises the /api/state endpoints that the persistent
        // UI filter (`useAppState('items.showCompleted', true)`) uses.
        // The state API stores values as JSON-stringified strings on
        // the wire, so this also tests the encode/decode layer.
        const stateKey = 'smoke.testFlag';
        const stateValue = { flag: true, ts: Date.now() };
        await saveState(stateKey, stateValue);
        const allState = await loadAllState();
        expect(allState).toHaveProperty(stateKey);
        expect((allState[stateKey] as { flag: boolean }).flag).toBe(true);
        await deleteState(stateKey);
        const afterDelete = await loadAllState();
        expect(afterDelete).not.toHaveProperty(stateKey);

        // Sub-step 9: anonymous request must raise AuthError. We
        // briefly clear the store so listItems() picks up no token,
        // then restore it for the next assertion.
        clearToken();
        await expect(listItems()).rejects.toBeInstanceOf(AuthError);
        setToken(token);

        // Sub-step 10: explicit invalid token must also raise
        // AuthError — the override path (`{token: 'bogus'}`) is
        // tested separately because it bypasses the store.
        await expect(
          listItems({ token: 'not-a-real-token' }),
        ).rejects.toBeInstanceOf(AuthError);
      },
      // Generous timeout — every step crosses the network.
      30_000,
    );
  },
);
