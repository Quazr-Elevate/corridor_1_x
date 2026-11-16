import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests for the Cor1x frontend.
 *
 * These drive a real browser against a real Next.js server talking to a
 * real backend — nothing is mocked. `scripts/e2e.sh` boots both and sets
 * the variables below; `npx playwright test` also works on its own if a
 * frontend is already running on E2E_BASE_URL.
 *
 * Required environment:
 *   E2E_BASE_URL     frontend origin (default http://127.0.0.1:3100)
 *   E2E_API_URL      backend origin, for seeding through the API
 *                    (default http://127.0.0.1:8001)
 *   E2E_ADMIN_EMAIL  bootstrap admin, for the console specs
 *   E2E_ADMIN_PASSWORD
 *
 * The backend must run with DEBUG=true: the signup screen then shows the
 * emailed code, which is how these tests complete a real signup.
 */
const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  // Scenarios share one backend database, so they run one at a time.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["list"],
    ["json", { outputFile: "e2e-results/results.json" }],
    ["html", { outputFolder: "e2e-results/html", open: "never" }],
  ],
  outputDir: "e2e-results/artifacts",
  use: {
    baseURL,
    trace: "off",
    screenshot: "only-on-failure",
    video: "off",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    // The app animates generously (framer-motion plus CSS transitions).
    // Asking for reduced motion lets MotionProvider settle the page so
    // Playwright isn't waiting for elements to stop moving.
    reducedMotion: "reduce",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
      // Only the responsive scenarios need a second form factor.
      testMatch: /responsive\.spec\.ts/,
    },
  ],
});
