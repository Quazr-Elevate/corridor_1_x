"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

const FOCUSABLE = "input:not([type=hidden]):not([disabled]), select, textarea, button:not([disabled]), [tabindex]:not([tabindex='-1'])";

/**
 * Scroll an element into view and focus it. `id` may point at an input
 * itself or at a wrapper — then the first focusable descendant (or the
 * checked radio) gets focus. Returns whether the element was found.
 */
export function focusField(id: string): boolean {
  if (typeof document === "undefined" || !id) return false;
  const el = document.getElementById(id);
  if (!el) return false;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  const target =
    el.matches(FOCUSABLE)
      ? el
      : el.querySelector<HTMLElement>("[aria-checked=true]") ?? el.querySelector<HTMLElement>(FOCUSABLE) ?? el;
  // Let the smooth scroll start before focusing so the browser doesn't
  // jump straight to the element.
  window.setTimeout(() => target.focus({ preventScroll: true }), 320);
  return true;
}

/**
 * On mount (and whenever the hash or `?focus=` changes), focus the field the
 * URL points at:
 *   • `/dashboard/account#phone`            → element id "phone"
 *   • `/dashboard/account?focus=phone`      → same, legacy form
 * Retries briefly so fields rendered after data hydration are still found.
 */
export function useFocusField() {
  const params = useSearchParams();
  const focusId = params?.get("focus") ?? null;

  useEffect(() => {
    let timer: number | undefined;
    const run = (id: string | null, attempt = 0) => {
      if (!id || id === "__guard") return;
      if (focusField(id)) return;
      if (attempt < 8) timer = window.setTimeout(() => run(id, attempt + 1), 150);
    };
    const fromUrl = () => focusId ?? (window.location.hash ? decodeURIComponent(window.location.hash.slice(1)) : null);
    timer = window.setTimeout(() => run(fromUrl()), 120);
    const onHash = () => run(fromUrl());
    window.addEventListener("hashchange", onHash);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("hashchange", onHash);
    };
  }, [focusId]);
}
