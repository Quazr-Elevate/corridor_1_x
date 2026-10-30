"use client";

import type { Me } from "@/lib/api";
import { commodityPhoto } from "@/lib/media";
import { focusField } from "@/lib/useFocusField";
import { DETAILS_PATH, MANDATORY_FIELDS, PASSPORT_PATH, fieldHref } from "@/lib/verification";
import type { Command } from "./CommandPalette";
import { LENS_LABEL, type Lens } from "./lens";
import { LotThumb } from "./LotThumb";

/**
 * Everything the palette can do, built from the signed-in trader's real
 * state: pages, every Passport section and mandatory field (with whether
 * it is still needed), market commodities, settings. Nothing here has a
 * side effect beyond navigation, the lens, or signing out.
 */

const MARKET_COMMODITIES = ["Rice", "Sugar", "Wheat", "Pulses", "Spices"] as const;

const PASSPORT_SECTIONS = [
  { tab: "primary", label: "Primary info", keywords: "you contact name phone position" },
  { tab: "company", label: "Company info", keywords: "legal name industry countries website" },
  { tab: "business", label: "Business profile", keywords: "trade position seller buyer markets objective" },
  { tab: "certifications", label: "Documents & certificates", keywords: "stamps upload gst fssai iec" },
] as const;

/**
 * Navigate — or, when the target is on the page you're on, scroll to it
 * (focusing the field) without a reload and without the unsaved prompt.
 */
export function navigateTo(href: string, push: (href: string) => void, confirmIfDirty: (nav: () => void) => boolean) {
  const url = new URL(href, window.location.origin);
  if (url.pathname === window.location.pathname) {
    const hash = url.hash.slice(1);
    if (hash && document.getElementById(hash)) {
      focusField(hash);
      return;
    }
    const tab = url.searchParams.get("tab");
    const section = tab ? document.getElementById(`section-${tab}`) : null;
    if (section) {
      section.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (!hash && !tab && url.search === window.location.search) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
  }
  confirmIfDirty(() => push(href));
}

export function buildCommands({
  me,
  lens,
  setLens,
  go,
  signOut,
}: {
  me: Me | null;
  lens: Lens;
  setLens: (l: Lens) => void;
  go: (href: string) => void;
  signOut: () => void;
}): Command[] {
  const out: Command[] = [];
  const market: Command[] = [
    {
      id: "market-all",
      group: "Market",
      label: "All live lots",
      keywords: "market browse lots buy",
      icon: "grain",
      run: () => go("/products"),
    },
    ...MARKET_COMMODITIES.map<Command>((c) => ({
      id: `market-${c}`,
      group: "Market",
      label: `${c} lots`,
      keywords: `market ${c} commodity`,
      thumb: <LotThumb category={c} media={commodityPhoto(c)} size={22} radius={7} />,
      run: () => go(`/products?category=${encodeURIComponent(c)}`),
    })),
  ];

  if (!me) {
    out.push(
      { id: "go-market", group: "Go to", label: "Market", icon: "grain", run: () => go("/products") },
      { id: "go-signin", group: "Go to", label: "Sign in", icon: "key", keywords: "login", run: () => go("/login") },
      {
        id: "go-signup",
        group: "Go to",
        label: "Get verified — create an account",
        icon: "shield",
        keywords: "signup register",
        run: () => go("/signup"),
      },
      ...market,
    );
    return out;
  }

  const missing = me.verification.missing;
  const next = MANDATORY_FIELDS.find((f) => missing.includes(f.key));
  const other: Lens = lens === "selling" ? "buying" : "selling";

  // ── Do ──
  if (next && me.verification.status !== "pending_verification" && me.verification.status !== "verified") {
    out.push({
      id: "do-next-field",
      group: "Do",
      label: `Fill in ${next.label.toLowerCase()}`,
      keywords: "passport verify next field",
      icon: "pen",
      move: true,
      hint: "Your move",
      run: () => go(fieldHref(next)),
    });
  }
  out.push(
    {
      id: "do-new-listing",
      group: "Do",
      label: "New listing",
      keywords: "list a lot sell create product",
      icon: "plus",
      run: () => go("/dashboard/products/new"),
    },
    {
      id: "do-lens",
      group: "Do",
      label: `Switch to ${LENS_LABEL[other]}`,
      keywords: "lens mode selling buying",
      icon: "route",
      run: () => {
        setLens(other);
        go("/dashboard");
      },
    },
  );

  // ── Go to ──
  out.push(
    { id: "go-home", group: "Go to", label: "Corridor", hint: "Home", icon: "corridor", run: () => go("/dashboard") },
    { id: "go-market", group: "Go to", label: "Market", icon: "grain", run: () => go("/products") },
    {
      id: "go-listings",
      group: "Go to",
      label: "Listings",
      keywords: "my lots products",
      icon: "sack",
      run: () => go("/dashboard/products"),
    },
    {
      id: "go-passport",
      group: "Go to",
      label: "Passport",
      keywords: "account profile company verification",
      icon: "passport",
      run: () => go(PASSPORT_PATH),
    },
    {
      id: "go-settings",
      group: "Go to",
      label: "Settings & security",
      keywords: "password account",
      icon: "settings",
      run: () => go("/dashboard/settings"),
    },
  );

  // ── Passport: sections, then each mandatory field ──
  for (const s of PASSPORT_SECTIONS) {
    out.push({
      id: `pp-${s.tab}`,
      group: "Passport",
      label: s.label,
      keywords: `passport section ${s.keywords}`,
      icon: s.tab === "certifications" ? "doc-check" : "passport",
      run: () => go(`${DETAILS_PATH}?tab=${s.tab}`),
    });
  }
  for (const f of MANDATORY_FIELDS) {
    const needed = missing.includes(f.key);
    out.push({
      id: `field-${f.key}`,
      group: "Passport fields",
      label: f.label,
      keywords: `passport field verify ${f.section} ${f.anchor.replace(/-/g, " ")}`,
      icon: "pen",
      move: needed,
      hint: needed ? <span className="text-amber">Needed to verify</span> : "Filled",
      run: () => go(fieldHref(f)),
    });
  }

  out.push(...market);

  // ── Account ──
  out.push(
    {
      id: "acct-password",
      group: "Account",
      label: "Change password",
      keywords: "security settings",
      icon: "lock",
      run: () => go("/dashboard/settings#password"),
    },
    {
      id: "acct-signout",
      group: "Account",
      label: "Sign out",
      keywords: "logout leave",
      icon: "logout",
      run: signOut,
    },
  );

  return out;
}
