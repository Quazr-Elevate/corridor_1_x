import type { ReactNode } from "react";
import { RouteTransition } from "@/components/motion/RouteTransition";

// Re-mounted by Next.js on every navigation inside the market. TraderShell
// lives in layout.tsx, so the dock and top cluster stay put.
export default function MarketTemplate({ children }: { children: ReactNode }) {
  return <RouteTransition>{children}</RouteTransition>;
}
