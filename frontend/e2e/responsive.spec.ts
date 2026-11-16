/**
 * E2E-UI-5xx — the same pages on a phone, and the basics of accessible
 * markup. Runs under both the desktop and mobile projects.
 * Scenario IDs match docs/testing/SCENARIOS.md.
 */
import { expect, test } from "@playwright/test";
import { seedLot, seedVerifiedTrader } from "./support/api";
import { evaluateStable, gotoReady, signIn } from "./support/ui";

const PUBLIC_PAGES = ["/", "/products", "/login", "/signup", "/privacy", "/terms"];

test.describe("@responsive layout and markup", () => {
  test("E2E-UI-500 public pages fit the viewport without sideways scrolling", async ({ page }) => {
    for (const path of PUBLIC_PAGES) {
      await gotoReady(page, path);
      const overflow = await evaluateStable(page, () => {
        const doc = document.documentElement;
        return doc.scrollWidth - doc.clientWidth;
      });
      // A pixel or two of rounding is fine; a broken layout is not.
      expect(overflow, `${path} scrolls sideways by ${overflow}px`).toBeLessThanOrEqual(2);
    }
  });

  test("E2E-UI-510 every public page has exactly one top-level heading", async ({ page }) => {
    for (const path of PUBLIC_PAGES) {
      await gotoReady(page, path);
      await expect(page.getByRole("heading", { level: 1 }), `${path} has one h1`).toHaveCount(1);
    }
  });

  test("E2E-UI-520 forms label their fields", async ({ page }) => {
    for (const path of ["/login", "/signup", "/forgot-password"]) {
      await gotoReady(page, path);
      const unlabelled = await evaluateStable(page, () => {
        const fields = Array.from(document.querySelectorAll("input:not([type=hidden]), select, textarea"));
        return fields
          .filter((el) => {
            const id = el.getAttribute("id");
            const labelled =
              (id && document.querySelector(`label[for="${CSS.escape(id)}"]`)) ||
              el.getAttribute("aria-label") ||
              el.getAttribute("aria-labelledby") ||
              el.closest("label");
            return !labelled;
          })
          .map((el) => el.outerHTML.slice(0, 120));
      });
      expect(unlabelled, `${path} has unlabelled fields`).toEqual([]);
    }
  });

  test("E2E-UI-530 images carry alt text", async ({ page }) => {
    for (const path of ["/", "/products"]) {
      await gotoReady(page, path);
      const missing = await evaluateStable(page, () =>
        Array.from(document.images)
          .filter((img) => !img.hasAttribute("alt"))
          .map((img) => img.currentSrc || img.src),
      );
      expect(missing, `${path} has images without an alt attribute`).toEqual([]);
    }
  });

  test("E2E-UI-540 the market and a lot page work on a phone", async ({ page }) => {
    const seller = await seedVerifiedTrader("ui540");
    const lot = await seedLot(seller);
    await seller.api.dispose();

    await gotoReady(page, "/products");
    await expect(page.getByRole("heading", { name: /the market/i })).toBeVisible();

    await gotoReady(page, `/products/${lot.id}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = await evaluateStable(
      page,
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(2);
  });

  test("E2E-UI-550 the dashboard works on a phone", async ({ page }) => {
    const trader = await seedVerifiedTrader("ui550");
    await signIn(page, trader);
    await trader.api.dispose();

    await gotoReady(page, "/dashboard");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = await evaluateStable(
      page,
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(2);
  });

  test("E2E-UI-560 keyboard users can reach the login form", async ({ page }) => {
    await gotoReady(page, "/login");
    await page.keyboard.press("Tab");
    await expect(async () => {
      const reached = await evaluateStable(page, () => {
        const el = document.activeElement;
        return !!el && el !== document.body;
      });
      expect(reached, "Tab must move focus into the page").toBeTruthy();
    }).toPass({ timeout: 15_000 });
  });
});
