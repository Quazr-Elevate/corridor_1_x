import type { ReactNode } from "react";
import { RouteTransition } from "@/components/motion/RouteTransition";

// Re-mounted by Next.js on every navigation inside the control tower.
// TowerShell (rail, status line) lives in layout.tsx and never moves.
export default function TowerTemplate({ children }: { children: ReactNode }) {
  return <RouteTransition>{children}</RouteTransition>;
}
