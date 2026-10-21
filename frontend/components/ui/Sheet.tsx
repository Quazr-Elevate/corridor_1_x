"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/cn";
import { IconButton } from "./Button";

/**
 * Sheet — a glass panel that floats over a scrim. Bottom sheet on phones,
 * centred dialog on wider screens. Esc and scrim-click close it; focus
 * moves into the sheet on open and returns on close.
 */
export function Sheet({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const reduce = useReducedMotion();
  const panelRef = useRef<HTMLDivElement>(null);
  const lastFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    lastFocus.current = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const t = window.setTimeout(() => {
      const el = panelRef.current?.querySelector<HTMLElement>(
        "[autofocus], input, textarea, select, button:not([data-close])",
      );
      (el ?? panelRef.current)?.focus();
    }, 30);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
      window.clearTimeout(t);
      lastFocus.current?.focus?.();
    };
  }, [open, onClose]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <AnimatePresence>
      {open ? (
        <div className="fixed inset-0 z-[80] flex items-end justify-center sm:items-center sm:p-6">
          <motion.div
            className="absolute inset-0 bg-[rgb(40_32_18/0.28)] backdrop-blur-[2px] [[data-surface=tower]_&]:bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
          />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={typeof title === "string" ? title : undefined}
            tabIndex={-1}
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: 16 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className={cn(
              "glass relative w-full rounded-t-sheet p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] outline-none sm:rounded-sheet sm:p-8",
              size === "sm" && "sm:max-w-[420px]",
              size === "md" && "sm:max-w-[520px]",
              size === "lg" && "sm:max-w-[720px]",
              "max-h-[92dvh] overflow-y-auto",
              className,
            )}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h2 className="t-title2 text-fg">{title}</h2>
                {description ? <p className="t-callout mt-2 text-fg-2">{description}</p> : null}
              </div>
              <IconButton icon="close" label="Close" onClick={onClose} data-close className="-mr-2 -mt-1 shrink-0" />
            </div>
            {children ? <div className="mt-6">{children}</div> : null}
            {footer ? <div className="mt-8 flex flex-wrap items-center justify-end gap-3">{footer}</div> : null}
          </motion.div>
        </div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
