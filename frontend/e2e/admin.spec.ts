/**
 * E2E-UI-4xx — the ops console (the "tower").
 *
 * The bootstrap admin is shared by the whole run, and five wrong passwords
 * would lock it for everyone, so the negative scenario uses an address
 * that was never an admin. Scenario IDs match docs/testing/SCENARIOS.md.
 */
import { expect, test, type Page } from "@playwright/test";
import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  fillPassport,
  seedTrader,
  submitForVerification,
} from "./support/api";
import { fillField, gotoReady, label } from "./support/ui";

async function signInAsAdmin(page: Page): Promise<void> {
  await gotoReady(page, "/admin/login");
  await expect(async () => {
    await fillField(page.getByLabel(label("Email")), ADMIN_EMAIL);
    await fillField(page.getByLabel(label("Password")), ADMIN_PASSWORD);
    await page.getByRole("button", { name: /sign in|open the tower|enter/i }).first().click();
    await expect(page).not.toHaveURL(/\/admin\/login/, { timeout: 15_000 });
  }).toPass({ timeout: 45_000 });
}

test.describe("@admin the ops console", () => {
  test("E2E-UI-400 the console is closed without an admin session", async ({ page }) => {
    await page.goto("/admin");
    // Either the console bounces to its own login, or it renders the login.
    await expect(page.getByRole("heading", { name: /open the tower|set your password/i })).toBeVisible({
      timeout: 20_000,
    });
  });

  test("E2E-UI-410 wrong admin credentials are refused", async ({ page }) => {
    await gotoReady(page, "/admin/login");
    // Never the real admin: five wrong tries would lock it for the suite.
    await fillField(page.getByLabel(label("Email")), "not-an-admin@cor1x.test");
    await fillField(page.getByLabel(label("Password")), "definitely-not-it");
    await page.getByRole("button", { name: /sign in|open the tower|enter/i }).first().click();

    await expect(page.getByRole("alert").first()).toBeVisible({ timeout: 20_000 });
    await expect(page).toHaveURL(/\/admin\/login/);
  });

  test("E2E-UI-420 an admin signs in and sees the tower", async ({ page }) => {
    await signInAsAdmin(page);
    await expect(page).toHaveURL(/\/admin/);
    // The dashboard shows live counts rather than an error state.
    await expect(page.getByText(/couldn’t|could not/i)).toHaveCount(0);
    await expect(page.getByRole("heading").first()).toBeVisible();
  });

  test("E2E-UI-430 a submitted company appears in the review queue", async ({ page }) => {
    const trader = await seedTrader("ui430");
    await fillPassport(trader);
    await submitForVerification(trader);
    await trader.api.dispose();

    await signInAsAdmin(page);
    await page.goto("/admin/verify");
    await expect(page.getByRole("button", { name: new RegExp(trader.company) })).toBeVisible({ timeout: 20_000 });
  });

  test("E2E-UI-440 ops approves a company from the queue", async ({ page }) => {
    const trader = await seedTrader("ui440");
    await fillPassport(trader);
    await submitForVerification(trader);

    await signInAsAdmin(page);
    await page.goto("/admin/verify");
    await page.getByRole("button", { name: new RegExp(trader.company) }).click();

    // Approving is a deliberate press-and-hold.
    const approve = page.getByRole("button", { name: /approve company/i });
    await expect(approve).toBeEnabled({ timeout: 20_000 });
    await approve.dispatchEvent("pointerdown");
    await page.waitForTimeout(2_500);
    await approve.dispatchEvent("pointerup").catch(() => {});

    // The decision reached the backend: the trader is verified.
    await expect(async () => {
      const me = await trader.api.get("/me");
      expect((await me.json()).status).toBe("verified");
    }).toPass({ timeout: 30_000 });

    await trader.api.dispose();
  });

  test("E2E-UI-450 the admin pages ops uses every day all render", async ({ page }) => {
    await signInAsAdmin(page);
    for (const path of ["/admin", "/admin/verify", "/admin/users", "/admin/docs", "/admin/kyb-types", "/admin/admins"]) {
      await page.goto(path);
      await expect(page).toHaveURL(new RegExp(path.replace(/\//g, "\\/")));
      await expect(page.getByText(/application error|something went wrong/i)).toHaveCount(0);
      await expect(page.locator("main, body").first()).toBeVisible();
    }
  });
});
