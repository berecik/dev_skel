/**
 * End-to-end Playwright tests for the dev_skel React skeleton.
 *
 * These tests drive the REAL production-built React app (served by
 * `vite preview`) against a REAL running backend. They verify that
 * the UI components actually work in a browser — form binding, button
 * clicks, DOM structure, CSS-driven visibility, localStorage-backed
 * JWT persistence, and the wrapper-shared `/api/state` persistent
 * filter all get exercised.
 *
 * The cross-stack integration runner starts the backend, builds the
 * frontend, launches `vite preview`, then invokes Playwright with
 * `PLAYWRIGHT_BASE_URL` and `BACKEND_URL` set. These tests are NOT
 * run during `npm test` (that's vitest); they only run when the
 * runner calls `npx playwright test` explicitly.
 *
 * Each test registers its own user (`playwright-e2e-user`) so it
 * never collides with the Python pre-flight or the vitest smoke
 * users.
 */

import { expect, test } from '@playwright/test';

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';
const E2E_USERNAME = 'playwright-e2e-user';
const E2E_PASSWORD = 'playwright-e2e-pw-12345';
const E2E_EMAIL = 'playwright-e2e@example.com';
const E2E_ITEM_NAME = 'Playwright test item';
const E2E_ITEM_DESC = 'Created by the Playwright E2E test';

/**
 * Register a fresh user via the backend's `/api/auth/register` endpoint.
 * This mirrors the raw-fetch register helper in the vitest smoke.
 */
async function registerUser(): Promise<void> {
  const response = await fetch(`${BACKEND_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: E2E_USERNAME,
      email: E2E_EMAIL,
      password: E2E_PASSWORD,
      password_confirm: E2E_PASSWORD,
    }),
  });
  // 201 = new user created; 400 = user already exists (idempotent
  // on retry). Anything else is unexpected.
  if (response.status !== 201 && response.status !== 400) {
    const text = await response.text().catch(() => '');
    throw new Error(`register expected 201/400, got ${response.status}: ${text}`);
  }
}

test('full user journey: login → create → complete → persistent filter', async ({
  page,
}) => {
  // ── Step 0: register a test user via the backend API ──────────
  await registerUser();

  // ── Step 1: LOGIN ─────────────────────────────────────────────
  await page.goto('/');

  // The app should show the LoginForm when no JWT is stored.
  await expect(
    page.getByRole('heading', { name: /sign in/i }),
  ).toBeVisible();

  // Fill in the credentials and submit.
  await page.getByLabel(/username/i).fill(E2E_USERNAME);
  await page.getByLabel(/password/i).fill(E2E_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();

  // After login the authenticated UI should appear.
  await expect(page.getByText('dev_skel React')).toBeVisible();
  await expect(
    page.getByRole('heading', { name: /items/i }),
  ).toBeVisible({ timeout: 10_000 });

  // The "Sign out" button proves we're in the authenticated branch.
  await expect(
    page.getByRole('button', { name: /sign out/i }),
  ).toBeVisible();

  // ── Step 2: CREATE an item ────────────────────────────────────
  await page.getByLabel(/^name$/i).fill(E2E_ITEM_NAME);
  await page.getByLabel(/description/i).fill(E2E_ITEM_DESC);
  await page.getByRole('button', { name: /create item/i }).click();

  // The new item should appear in the list.
  await expect(page.getByText(E2E_ITEM_NAME)).toBeVisible({
    timeout: 10_000,
  });

  // ── Step 3: COMPLETE the item ─────────────────────────────────
  // Click "Mark complete" on the item we just created.
  await page
    .getByRole('button', { name: /mark complete/i })
    .first()
    .click();

  // The "✓ done" badge should appear (replaces the button).
  await expect(page.getByText('✓ done').first()).toBeVisible({
    timeout: 10_000,
  });

  // ── Step 4: PERSISTENT FILTER ─────────────────────────────────
  // The "Show completed" checkbox defaults to checked (true).
  const checkbox = page.getByLabel(/show completed/i);
  await expect(checkbox).toBeChecked();

  // Uncheck it — the completed item should disappear.
  await checkbox.uncheck();
  await expect(page.getByText(E2E_ITEM_NAME)).not.toBeVisible();

  // Reload the page. The JWT is in localStorage so we stay logged
  // in, and the filter state is in /api/state so it should persist.
  await page.reload();

  // Wait for the authenticated UI to reappear (the app hydrates the
  // JWT from localStorage and fetches items + state on load).
  await expect(
    page.getByRole('heading', { name: /items/i }),
  ).toBeVisible({ timeout: 10_000 });

  // The checkbox should still be unchecked (persisted via /api/state).
  await expect(page.getByLabel(/show completed/i)).not.toBeChecked();

  // The completed item should still be hidden.
  await expect(page.getByText(E2E_ITEM_NAME)).not.toBeVisible();

  // Re-check the checkbox to confirm the filter toggle still works
  // after a reload.
  await page.getByLabel(/show completed/i).check();
  await expect(page.getByText(E2E_ITEM_NAME)).toBeVisible();
});
