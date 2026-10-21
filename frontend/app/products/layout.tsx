import type { ReactNode } from "react";
import { TraderShell } from "@/components/shell/TraderShell";

// The market is public: anonymous visitors get signed-out chrome, signed-in
// traders get the full dock.
export default function MarketLayout({ children }: { children: ReactNode }) {
  return <TraderShell requireAuth={false}>{children}</TraderShell>;
}
