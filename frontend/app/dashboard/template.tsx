import type { ReactNode } from "react";
import { RouteTransition } from "@/components/motion/RouteTransition";

// Re-mounted by Next.js on every navigation inside /dashboard. TraderShell
// (dock + top cluster) lives in layout.tsx, so only the page content moves.
export default function DashboardTemplate({ children }: { children: ReactNode }) {
  return <RouteTransition>{children}</RouteTransition>;
}
