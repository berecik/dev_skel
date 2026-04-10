/**
 * Playwright configuration for the dev_skel React skeleton.
 *
 * The cross-stack integration runner (`_bin/test-react-*-integration`)
 * owns the server lifecycle: it starts the backend, runs `npm run build`,
 * then launches `vite preview` and invokes Playwright. So we do NOT
 * declare a `webServer` here — the runner passes the correct base URL
 * via the `PLAYWRIGHT_BASE_URL` environment variable.
 *
 * When developing locally you can still run the E2E tests standalone:
 *
 *     PLAYWRIGHT_BASE_URL=http://localhost:4173 npx playwright test
 *
 * (after running `npm run build && npx vite preview` in another
 * terminal).
 */

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  // One test at a time — each step depends on prior state (login →
  // create → complete → filter).
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'list' : 'html',
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:4173',
    // Capture traces on failure so CI artifacts are debuggable.
    trace: 'on-first-retry',
    // Headless by default; toggle with `--headed` for local debugging.
    headless: true,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Disable CORS enforcement so the browser can talk to the
        // backend on a different port without needing CORS headers on
        // every dev_skel backend. In production, a reverse proxy or
        // CORS middleware would handle this; in the E2E test we own
        // the browser and control its security policy directly.
        launchOptions: {
          args: ['--disable-web-security'],
        },
      },
    },
  ],
});
