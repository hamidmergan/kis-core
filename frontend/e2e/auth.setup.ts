import { test as setup, expect } from "@playwright/test";

const STATE = "e2e/.auth/state.json";

/**
 * Log in once via the real LDAP form and persist the session cookie so every
 * chat spec starts authenticated. Credentials default to the seeded dev user
 * `a`/`a` (the workspace owner); override with E2E_USER / E2E_PASS.
 */
setup("authenticate", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#username");
  await page.fill("#username", process.env.E2E_USER ?? "a");
  await page.fill("#password", process.env.E2E_PASS ?? "a");
  await page.locator('button[type="submit"]').click();

  // Login does a hard nav to "/"; we're authenticated once the form is gone.
  await page.waitForURL((url) => !url.pathname.includes("login"), { timeout: 30_000 });
  await expect(page.locator("#username")).toHaveCount(0);

  await page.context().storageState({ path: STATE });
});
