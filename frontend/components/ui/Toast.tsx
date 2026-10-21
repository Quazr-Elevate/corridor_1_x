"use client";

import { AnimatePresence, motion } from "framer-motion";
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";

type Tone = "default" | "verified" | "frozen";
interface ToastItem {
  id: number;
  message: ReactNode;
  tone: Tone;
}

const ToastCtx = createContext<(message: ReactNode, tone?: Tone) => void>(() => {});

/** Glass toasts, top-centre. `useToast()("Saved", "verified")`. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const seq = useRef(0);
  const push = useCallback((message: ReactNode, tone: Tone = "default") => {
    const id = ++seq.current;
    setItems((xs) => [...xs.slice(-2), { id, message, tone }]);
    window.setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 3800);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 top-[max(1rem,env(safe-area-inset-top))] z-[90] flex flex-col items-center gap-2 px-4"
      >
        <AnimatePresence>
          {items.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: -12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              className="glass pointer-events-auto flex items-center gap-2.5 rounded-full py-2.5 pl-3 pr-4 text-[14px] font-medium text-fg"
            >
              <span
                className={cn(
                  "grid size-6 place-items-center rounded-full",
                  t.tone === "verified" && "bg-lime text-ink",
                  t.tone === "frozen" && "bg-danger-soft text-danger",
                  t.tone === "default" && "solid",
                )}
              >
                <Icon name={t.tone === "frozen" ? "alert" : "check"} size={13} strokeWidth={2} />
              </span>
              {t.message}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  return useContext(ToastCtx);
}
