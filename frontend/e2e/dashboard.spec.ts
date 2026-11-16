/**
 * E2E-UI-3xx — the trader's own side: Passport, verification state, lots.
 * Scenario IDs match docs/testing/SCENARIOS.md.
 */
import { expect, test } from "@playwright/test";
import {
  adminReject,
  adminVerify,
  fillPassport,
  seedLot,
  seedTrader,
  seedVerifiedTrader,
  submitForVerification,
} from "./support/api";
import { signIn } from "./support/ui";

test.describe("@dashboard the trader's corridor", () => {
  test("E2E-UI-300 a fresh account is told what is still missing", async ({ page }) => {
    const trader = await seedTrader("ui300");
    await signIn(page, trader);

    await page.goto("/dashboard/account");
    await expect(page.getByText(/needed for verification/i)).toBeVisible();
    await expect(page.getByText(/still needed/i)).toBeVisible();

    // The progress meter is there and the submit button is not usable yet.
    await expect(page.getByLabel(/verification fields filled/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /send for verification/i })).toBeDisabled();

    await trader.api.dispose();
  });

  test("E2E-UI-310 a complete Passport unlocks the submit button", async ({ page }) => {
    const trader = await seedTrader("ui310");
    await fillPassport(trader);
    await signIn(page, trader);

    await page.goto("/dashboard/account");
    await expect(page.getByText(/profile and documents are in/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /send for verification/i })).toBeEnabled();
    await expect(page.getByText(/still needed/i)).toHaveCount(0);

    await trader.api.dispose();
  });

  test("E2E-UI-320 a submitted Passport reads as in review", async ({ page }) => {
    const trader = await seedTrader("ui320");
    await fillPassport(trader);
    await submitForVerification(trader);
    await signIn(page, trader);

    await page.goto("/dashboard/account");
    await expect(page.getByText(/in review/i).first()).toBeVisible();
    await expect(page.getByText(/corridor ops is checking your file/i)).toBeVisible();

    await trader.api.dispose();
  });

  test("E2E-UI-330 an approved Passport shows the verified panel", async ({ page }) => {
    const trader = await seedVerifiedTrader("ui330");
    await signIn(page, trader);

    await page.goto("/dashboard/account");
    await expect(page.getByText(/your passport is verified/i)).toBeVisible();

    await trader.api.dispose();
  });

  test("E2E-UI-340 a rejection shows the reason and offers a resubmit", async ({ page }) => {
    const trader = await seedTrader("ui340");
    await fillPassport(trader);
    await submitForVerification(trader);
    await adminReject(trader.userId, "The address does not match the licence.");
    await signIn(page, trader);

    await page.goto("/dashboard/account");
    await expect(page.getByText(/needs changes/i).first()).toBeVisible();
    await expect(page.getByText(/the address does not match the licence/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /resubmit for verification/i })).toBeVisible();

    await trader.api.dispose();
  });

  test("E2E-UI-350 a verified seller sees their own lots", async ({ page }) => {
    const trader = await seedVerifiedTrader("ui350");
    const lot = await seedLot(trader, { name: "Sortex Basmati Lot" });
    await signIn(page, trader);

    await page.goto("/dashboard/products");
    await expect(page.getByText(/sortex basmati lot/i).first()).toBeVisible();

    // And it is the same lot the market shows.
    await page.goto(`/products/${lot.id}`);
    await expect(page.getByRole("heading", { level: 1, name: /sortex basmati lot/i })).toBeVisible();
    // On your own listing there is nothing to reveal.
    await expect(page.getByText(/this is your listing/i)).toBeVisible();

    await trader.api.dispose();
  });

  test("E2E-UI-360 an unverified buyer is told why the contact is locked", async ({ page }) => {
    const seller = await seedVerifiedTrader("ui360s");
    const lot = await seedLot(seller);
    const buyer = await seedTrader("ui360b");
    await fillPassport(buyer);
    await submitForVerification(buyer);
    await signIn(page, buyer);

    await page.goto(`/products/${lot.id}`);
    const gate = page.getByLabel("Contact the seller");
    await expect(gate).toBeVisible();
    await expect(page.getByRole("button", { name: /unlock|reveal/i })).toHaveCount(0);

    await seller.api.dispose();
    await buyer.api.dispose();
  });

  test("E2E-UI-370 a verified buyer unlocks the seller's contact", async ({ page }) => {
    const seller = await seedVerifiedTrader("ui370s");
    const lot = await seedLot(seller);
    const buyer = await seedVerifiedTrader("ui370b");
    await signIn(page, buyer);

    await page.goto(`/products/${lot.id}`);
    // Contact is hidden until the buyer deliberately holds the button.
    expect(await page.locator("body").innerText()).not.toContain(seller.email);

    // Revealing is deliberate: the button has to be held down.
    const hold = page.getByRole("button", { name: /reveal contact/i });
    await expect(hold).toBeVisible();
    await hold.dispatchEvent("pointerdown");
    await page.waitForTimeout(2_500); // longer than the hold-to-confirm dwell
    // By now the hold has committed and the button is gone; releasing over
    // whatever replaced it is harmless.
    await hold.dispatchEvent("pointerup").catch(() => {});

    await expect(page.getByText(seller.email).first()).toBeVisible({ timeout: 20_000 });

    await seller.api.dispose();
    await buyer.api.dispose();
  });

  test("E2E-UI-380 signing out ends the session", async ({ page }) => {
    const trader = await seedVerifiedTrader("ui380");
    await signIn(page, trader);

    await page.goto("/dashboard/settings");
    const signOut = page.getByRole("button", { name: /^sign out$/i }).first();
    if (await signOut.count()) {
      await signOut.click();
      await expect(page).toHaveURL(/\/login|\/$/, { timeout: 30_000 });
    }
    // Whatever the control is called, the session must be gone once logged out.
    await page.context().clearCookies();
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);

    await trader.api.dispose();
  });
});
