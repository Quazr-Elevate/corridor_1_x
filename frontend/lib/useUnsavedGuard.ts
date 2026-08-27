"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createElement } from "react";

/**
 * Cross-component "you have unsaved changes" flag.
 *
 * The provider owns the flag + installs a `beforeunload` listener that covers
 * tab close / refresh / external navigation. In-app navigation (sidebar
 * links, back buttons) is opt-in: components call `confirmIfDirty(cb)` from
 * the hook before doing the navigation.
 */

interface Ctx {
  isDirty: boolean;
  setDirty: (d: boolean) => void;
  /** Runs `nav` immediately if not dirty, else prompts. Returns whether it ran. */
  confirmIfDirty: (nav: () => void) => boolean;
}

const UnsavedGuardContext = createContext<Ctx>({
  isDirty: false,
  setDirty: () => {},
  confirmIfDirty: (nav) => {
    nav();
    return true;
  },
});

export function UnsavedGuardProvider({ children }: { children: ReactNode }) {
  const [isDirty, setDirty] = useState(false);

  // Warn on hard navigations (refresh, close tab, url bar edit).
  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // The browser only shows its own generic string in modern browsers,
      // but returnValue must be set for the dialog to appear at all.
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  // Guard the browser's Back/Forward buttons via popstate. We push a sentinel
  // history entry (with a distinct hash so browsers keep it as its own entry)
  // when dirty flips on, so the first back click is absorbed by our handler.
  // On confirm, we replay the back navigation manually — the bypass ref keeps
  // the resulting popstate from re-prompting.
  const bypassRef = useRef(false);
  useEffect(() => {
    if (!isDirty) return;
    const originalHref = window.location.href;
    window.history.pushState(
      { __unsavedSentinel: true },
      "",
      window.location.pathname + window.location.search + "#__guard",
    );

    const onPop = () => {
      if (bypassRef.current) {
        bypassRef.current = false;
        return;
      }
      const ok = window.confirm(
        "You have unsaved changes. Leave without saving?",
      );
      if (ok) {
        // The pop already consumed the sentinel; step back once more to reach
        // the page the user actually wanted. Set bypass, then fire back on a
        // task so Next.js's own popstate listener finishes with the current
        // pop before we fire another. Don't touch dirty here — the form will
        // unmount on nav and its useDirtyFlag cleanup will clear it.
        bypassRef.current = true;
        window.setTimeout(() => window.history.back(), 20);
      } else {
        // Re-plant the sentinel so subsequent back clicks keep prompting.
        window.history.pushState(
          { __unsavedSentinel: true },
          "",
          window.location.pathname + window.location.search + "#__guard",
        );
      }
    };
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      // If we still have the sentinel URL in the address bar (e.g. save
      // succeeded without a navigation), quietly wipe the #__guard hash so
      // the user's URL doesn't stay marked. Uses replaceState so we don't
      // add another history entry.
      if (window.location.hash === "#__guard") {
        window.history.replaceState({}, "", originalHref);
      }
    };
  }, [isDirty]);

  const confirmIfDirty = useCallback(
    (nav: () => void) => {
      if (!isDirty) {
        nav();
        return true;
      }
      const ok = window.confirm(
        "You have unsaved changes. Leave without saving?",
      );
      if (ok) {
        setDirty(false);
        nav();
      }
      return ok;
    },
    [isDirty],
  );

  return createElement(
    UnsavedGuardContext.Provider,
    { value: { isDirty, setDirty, confirmIfDirty } },
    children,
  );
}

export function useUnsavedGuard() {
  return useContext(UnsavedGuardContext);
}

/**
 * Sync a component-local dirty flag into the provider. Cleans up on unmount
 * so leaving the page implicitly clears the flag.
 */
export function useDirtyFlag(dirty: boolean) {
  const { setDirty } = useUnsavedGuard();
  useEffect(() => {
    setDirty(dirty);
    return () => setDirty(false);
  }, [dirty, setDirty]);
}
