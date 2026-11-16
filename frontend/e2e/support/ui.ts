/** Browser-side helpers shared by the frontend E2E specs. */
import { expect, type Locator, type Page } from "@playwright/test";
import { PASSWORD, type SeededTrader } from "./api";

/**
 * Wait until the client runtime has taken over the page.
 *
 * Next.js streams server HTML first: the form is on screen and fillable
 * before React has attached to it, and anything typed in that window is
 * in the DOM but not in React state — the submit then fails validation as
 * if the fields were empty. `window.next` appears with the client runtime,
 * and two animation frames give React its first commit.
 */
export async function hydrated(page: Page): Promise<void> {
  // A redirect (the dashboard gate, say) can tear the context down
  // mid-check; settle on the page we actually landed on and try again.
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await page.waitForFunction(() => "next" in window, null, { timeout: 15_000 });
      await page.evaluate(
        () => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))),
      );
      return;
    } catch (error) {
      if (attempt === 2) throw error;
      await page.waitForLoadState("domcontentloaded");
    }
  }
}

/**
 * Open a page and wait for it to be interactive.
 *
 * A navigation started while the previous page is still settling (route
 * prefetch, the service worker registering) aborts with ERR_ABORTED, which
 * says nothing about the page being tested — so try again.
 */
export async function gotoReady(page: Page, path: string): Promise<void> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await page.goto(path, { waitUntil: "domcontentloaded" });
      break;
    } catch (error) {
      if (attempt === 2 || !String(error).includes("ERR_ABORTED")) throw error;
    }
  }
  await hydrated(page);
}

/** A field's accessible name — required fields render a trailing "*". */
export function label(name: string): RegExp {
  return new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\*?$`, "i");
}

/**
 * Type into a React-controlled field and make sure the value stuck.
 *
 * Every form here is a client component with controlled inputs. Typing in
 * the gap between the server HTML arriving and React hydrating is silently
 * undone — the field re-renders empty from state. Filling until the value
 * survives keeps the scenarios about the product instead of about
 * hydration races.
 */
export async function fillField(field: Locator, value: string): Promise<void> {
  await expect(async () => {
    await field.fill(value);
    await expect(field).toHaveValue(value, { timeout: 1_000 });
  }).toPass({ timeout: 20_000 });
}

/**
 * Sign in through the real login form.
 *
 * `next` is where the app should land afterwards (the login screen honours
 * `?next=`), so a spec can assert it got there.
 */
export async function signIn(page: Page, trader: SeededTrader, next = "/dashboard"): Promise<void> {
  if (page.url().includes("/login")) await hydrated(page);
  else await gotoReady(page, "/login");
  await submitForm(
    page,
    async () => {
      await fillField(page.getByLabel(label("Work email")), trader.email);
      await fillField(page.getByLabel(label("Password")), PASSWORD);
    },
    page.getByRole("button", { name: /sign in/i }),
    async () => expect(page).toHaveURL(new RegExp(next.replace(/\//g, "\\/")), { timeout: 15_000 }),
  );
}

/**
 * Fill a form and submit it until the app actually responds.
 *
 * Hydration is the reason for the retry: if React attaches between the
 * typing and the click, the submit runs against empty state and the form
 * answers with "this field is required" for fields the browser can see
 * filled in. Retrying the whole fill-and-submit makes that invisible to
 * the scenario, and a form that is genuinely broken still fails.
 */
export async function submitForm(
  page: Page,
  fill: () => Promise<void>,
  submit: Locator,
  expectation: () => Promise<unknown>,
  timeout = 45_000,
): Promise<void> {
  await expect(async () => {
    await fill();
    await submit.click();
    await expectation();
  }).toPass({ timeout });
}

/**
 * Type a term into the market's search box and apply it.
 *
 * The filter bar is a client component: until React hydrates, a submit is
 * a plain browser form post that changes nothing (the input carries no
 * `name`). Retrying the fill-and-click until the URL actually carries `q`
 * keeps the scenario about search rather than about hydration timing.
 */
export async function searchMarket(page: Page, term: string): Promise<void> {
  const search = page.getByLabel("Search lots");
  // Exact: once the box has text a "Clear search" button appears too.
  const go = page.getByRole("search").getByRole("button", { name: "Search", exact: true });
  await expect(async () => {
    await search.fill(term);
    await go.click();
    await expect(page).toHaveURL(/[?&]q=/, { timeout: 3_000 });
  }).toPass({ timeout: 30_000 });
  await expect(search).toHaveValue(term);
}

/**
 * Run a snippet in the page, retrying if a navigation tears the context
 * down underneath it (Next prefetches routes as links come into view).
 */
export async function evaluateStable<T>(page: Page, fn: () => T): Promise<T> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await page.evaluate(fn);
    } catch (error) {
      if (attempt === 2 || !String(error).includes("Execution context was destroyed")) throw error;
      await page.waitForLoadState("domcontentloaded");
    }
  }
  throw new Error("unreachable");
}
