import { defineConfig, devices } from "@playwright/test";

/**
 * Live smoke tests for the AI-assistant chat (generic + specific paths).
 *
 * These run against the ALREADY-RUNNING dev stack (frontend :3001, backend
 * :8000) — they do NOT start a server. The answers come from the real LLM, so
 * assertions check the SHAPE of the result (an answer arrived, a citation chip
 * exists, the viewer navigated/highlighted) — never the exact wording.
 *
 * Prereq: the dev stack is up and the workspace from E2E_WORKSPACE has ready
 * sources. Auth runs once (auth.setup.ts) and is reused via storageState.
 */
const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  // Live LLM answers are slow; give each test room and run serially so the
  // single shared chat backend isn't hammered in parallel.
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    {
      name: "chat",
      testMatch: /.*\.spec\.ts/,
      dependencies: ["setup"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/.auth/state.json",
      },
    },
  ],
});
