import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for Nexus Care AI e2e tests.
 *
 * The tests assume:
 *   - Postgres is up (`make db-up` from repo root)
 *   - Migrations have run (`make db-migrate`)
 *   - The sandbox tenant is seeded (`make db-seed`)
 *   - The API is running on http://localhost:18001
 *
 * The webServer block boots the Next.js dev server automatically when you run
 * `bun run test:e2e`. The API needs to be running independently — Playwright's
 * webServer hook can only manage one process, and the API is the more
 * sensitive one (we don't want test invocations spinning up the FastAPI
 * server with possibly-stale env state).
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false, // single-tenant fixtures, keep deterministic
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : [["list"]],
  use: {
    baseURL: "http://localhost:3001",
    trace: "on-first-retry",
    actionTimeout: 5_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "bun run dev",
    url: "http://localhost:3001",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
