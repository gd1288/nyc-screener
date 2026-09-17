import { defineConfig } from "@playwright/test";

// Smoke-test only: a handful of specs that confirm each page renders against a seeded backend,
// not a full end-to-end suite. The backend (pointed at a seeded test DB) is started separately by
// CI, or by hand in development — see .github/workflows/ci.yml and backend/tests/fixtures/seed.py.
//
// Port is overridable via PORT (also read by `next start` itself) so a local run doesn't collide
// with an already-running dev server on 3000 -- e.g. `PORT=3001 npm run test:e2e`.
const port = process.env.PORT ?? "3000";
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["html", { open: "never" }], ["list"]] : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run start",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
