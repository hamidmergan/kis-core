import { defineConfig } from "vitest/config";

// Unit tests for pure frontend logic. Scoped to src/ so the Playwright E2E
// specs under e2e/ are NOT picked up (those run via `npm run test:e2e`).
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["node_modules", ".next", "e2e"],
  },
});
