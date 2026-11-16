/**
 * E2E-UI-1xx — what a stranger sees: the landing page, the market, a lot.
 * Scenario IDs match docs/testing/SCENARIOS.md.
 */
import { expect, test } from "@playwright/test";
import { lotName, seedLot, seedVerifiedTrader } from "./support/api";
import { gotoReady, searchMarket } from "./support/ui";

test.describe("@public the open corridor", () => {
  test("E2E-UI-100 the landing page invites you in", async ({ page }) => {
    await gotoReady(page, "/");

    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("link", { name: /sign in/i }).first()).toBeVisible();

    // The way out of the landing page works. Retried: a click that lands
    // while the page is still settling does nothing at all.
    const toMarket = page.getByRole("link", { name: "Market", exact: true }).first();
    await expect(async () => {
      await toMarket.click();
      await expect(page).toHaveURL(/\/products/, { timeout: 10_000 });
    }).toPass({ timeout: 45_000 });
    await expect(page.getByRole("heading", { name: /the market/i })).toBeVisible();
  });

  test("E2E-UI-110 an unknown URL shows the not-found page, not a crash", async ({ page }) => {
    const res = await page.goto("/no-such-page");
    expect(res?.status()).toBe(404);
    await expect(page.locator("body")).not.toContainText("Application error");
  });

  test("E2E-UI-120 policy pages are reachable", async ({ page }) => {
    for (const path of ["/privacy", "/terms"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    }
  });

  test("E2E-UI-130 a verified seller's lot shows up and can be searched", async ({ page }) => {
    const seller = await seedVerifiedTrader("ui130");
    const rice = lotName("Zephyrbasmati");
    const wheat = lotName("Quirkdurum");
    await seedLot(seller, { name: rice });
    await seedLot(seller, { name: wheat, category: "Wheat", originState: "Punjab" });

    await page.goto("/products");
    await expect(page.getByRole("link", { name: rice })).toBeVisible();

    // Search narrows the list to the matching lot.
    await searchMarket(page, rice);
    await expect(page.getByRole("link", { name: rice })).toBeVisible();
    await expect(page.getByRole("link", { name: wheat })).toHaveCount(0);

    // A search that matches nothing says so instead of looking broken.
    await searchMarket(page, "zzzzznothing");
    await expect(page.getByText(/no lots match/i)).toBeVisible();

    await seller.api.dispose();
  });

  test("E2E-UI-140 the lot page hides the seller behind a gate", async ({ page }) => {
    const seller = await seedVerifiedTrader("ui140");
    const name = lotName("Gated Basmati");
    const lot = await seedLot(seller, { name });

    await page.goto(`/products/${lot.id}`);
    await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();

    // The gate offers the two ways in, and nothing identifying leaks.
    const gate = page.getByRole("main");
    await expect(gate.getByRole("link", { name: /sign in to contact/i })).toBeVisible();
    await expect(gate.getByRole("link", { name: /get verified/i })).toBeVisible();
    const body = await page.locator("body").innerText();
    expect(body).not.toContain(seller.email);
    expect(body).not.toContain("Asha Rao");

    // "Sign in to contact" remembers where you were.
    await page.getByRole("link", { name: /sign in to contact/i }).click();
    await expect(page).toHaveURL(new RegExp(`/login\\?next=.*${lot.id}`));

    await seller.api.dispose();
  });

  test("E2E-UI-150 a lot that does not exist is a not-found page", async ({ page }) => {
    const res = await page.goto("/products/00000000-0000-4000-8000-000000000000");
    expect(res?.status()).toBe(404);
  });
});
