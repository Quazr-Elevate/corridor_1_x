"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

/**
 * When the URL carries `?focus=<inputId>`, wait for the form to mount, then
 * scroll that input into view, focus it, and pulse a highlight ring on its
 * field wrapper so the user can see where they landed.
 */
export function useFocusField() {
  const params = useSearchParams();
  const focusId = params?.get("focus") ?? null;

  useEffect(() => {
    if (!focusId) return;
    const t = window.setTimeout(() => {
      const el = document.getElementById(focusId);
      if (!el) return;
      const wrapper = el.closest("[data-field-wrapper]") ?? el.parentElement ?? el;
      wrapper.scrollIntoView({ behavior: "smooth", block: "center" });
      if (
        el instanceof HTMLInputElement ||
        el instanceof HTMLTextAreaElement ||
        el instanceof HTMLSelectElement
      ) {
        el.focus();
      }
      wrapper.classList.add("focus-pulse");
      window.setTimeout(() => {
        wrapper.classList.remove("focus-pulse");
      }, 1800);
    }, 250);
    return () => window.clearTimeout(t);
  }, [focusId]);
}
