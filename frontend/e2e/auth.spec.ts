/**
 * E2E-UI-2xx — getting an account and getting in.
 *
 * The signup scenario is a genuine end-to-end signup: the browser asks for
 * a code, the backend emails it, and (because the E2E backend runs with
 * DEBUG=true) the screen shows it, so the browser types it like a person
 * reading their inbox. Scenario IDs match docs/testing/SCENARIOS.md.
 */
import { expect, test, type Page } from "@playwright/test";
import { PASSWORD, seedTrader, seedVerifiedTrader, workEmail } from "./support/api";
import { fillField, gotoReady, label, signIn, submitForm } from "./support/ui";

/** Step one of the signup form: who you are and where to send the code. */
async function startSignup(page: Page, email: string): Promise<void> {
  await gotoReady(page, "/signup");
  await submitForm(
    page,
    async () => {
      await fillField(page.getByLabel(label("Full name")), "Asha Rao");
      await fillField(page.getByLabel(label("Company name")), `Kaveri Foods ${Date.now() % 100000} Pvt Ltd`);
      await fillField(page.getByLabel(label("Work email")), email);
    },
    page.getByRole("button", { name: /send code/i }),
    // Either the code screen, or the form's own answer to a bad address.
    async () =>
      expect(
        page
          .getByRole("heading", { name: /check your inbox/i })
          .or(page.getByRole("alert").filter({ hasText: /company email|personal addresses|not accepted/i }).first()),
      ).toBeVisible({ timeout: 10_000 }),
  );
}

test.describe("@auth signing up and in", () => {
  test("E2E-UI-200 a new company signs up and lands on its dashboard", async ({ page }) => {
    await startSignup(page, workEmail("ui200"));

    // The code screen. With DEBUG on, the emailed code is shown here.
    await expect(page.getByRole("heading", { name: /check your inbox/i })).toBeVisible();
    const shown = page.getByText(/^\d{6}$/).first();
    await expect(shown, "the backend must run with DEBUG=true for this scenario").toBeVisible();
    const code = (await shown.innerText()).trim();

    // From here the screens are client-rendered, so no hydration dance.
    // The code box submits itself once six digits are in.
    await fillField(page.getByLabel(label("Verification code")), code);

    // Password screen.
    await expect(page.getByRole("heading", { name: /create your password/i })).toBeVisible({ timeout: 20_000 });
    await fillField(page.getByLabel(label("Password")), PASSWORD);
    await fillField(page.getByLabel(label("Confirm password")), PASSWORD);
    // The real checkbox is visually hidden behind its styled label.
    await page.getByRole("checkbox").check({ force: true });
    await page.getByRole("button", { name: /create account/i }).click();

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 45_000 });
  });

  test("E2E-UI-210 free-mail addresses are refused on the signup screen", async ({ page }) => {
    await startSignup(page, "someone@gmail.com");

    await expect(
      page.getByRole("alert").filter({ hasText: /company email|personal addresses|not accepted/i }).first(),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: /check your inbox/i })).toHaveCount(0);
  });

  test("E2E-UI-220 a wrong code is rejected and keeps you on the code screen", async ({ page }) => {
    await startSignup(page, workEmail("ui220"));
    await expect(page.getByRole("heading", { name: /check your inbox/i })).toBeVisible();

    // Six digits submit themselves; a wrong code comes straight back.
    await fillField(page.getByLabel(label("Verification code")), "000000");
    await expect(page.getByRole("alert").first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("heading", { name: /create your password/i })).toHaveCount(0);
    await expect(page).not.toHaveURL(/\/dashboard/);
  });

  test("E2E-UI-230 an existing account signs in and reaches a private page", async ({ page }) => {
    const trader = await seedTrader("ui230");
    await trader.api.dispose();

    await signIn(page, trader);
    await page.goto("/dashboard/account");
    await expect(page).toHaveURL(/\/dashboard\/account/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("E2E-UI-240 a wrong password says so and keeps you out", async ({ page }) => {
    const trader = await seedTrader("ui240");
    await trader.api.dispose();

    await gotoReady(page, "/login");
    await fillField(page.getByLabel(label("Work email")), trader.email);
    await fillField(page.getByLabel(label("Password")), "definitely-not-it");
    await page.getByRole("button", { name: /sign in/i }).click();

    await expect(page.getByText(/don’t match|do not match|didn’t match/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("E2E-UI-250 a protected page sends an anonymous visitor to login and back", async ({ page }) => {
    await page.goto("/dashboard/products");
    await expect(page).toHaveURL(/\/login\?next=%2Fdashboard%2Fproducts/);

    const trader = await seedVerifiedTrader("ui250");
    await trader.api.dispose();

    // Signing in returns you to where you were going.
    await signIn(page, trader, "/dashboard/products");
  });

  test("E2E-UI-260 the forgot-password screen accepts an email", async ({ page }) => {
    const trader = await seedTrader("ui260");
    await trader.api.dispose();

    await gotoReady(page, "/login");
    await page.getByRole("link", { name: /forgot your password/i }).click();
    await expect(page).toHaveURL(/\/forgot-password/);

    await fillField(page.getByLabel(label("Work email")).or(page.getByLabel(/email/i)).first(), trader.email);
    await page.getByRole("button", { name: /send|reset|continue/i }).first().click();
    await expect(page.getByText(/if an account exists|code/i).first()).toBeVisible();
  });

  test("E2E-UI-270 signing in on a second browser signs the first one out", async ({ browser, page }) => {
    const trader = await seedTrader("ui270");
    await trader.api.dispose();

    await signIn(page, trader);

    // A second browser — one device per account, so this one wins.
    const second = await browser.newContext();
    const phone = await second.newPage();
    await signIn(phone, trader);

    // The first browser's session is gone: a protected page bounces to login.
    await page.goto("/dashboard/account");
    await expect(page).toHaveURL(/\/login/, { timeout: 30_000 });

    await second.close();
  });
});
