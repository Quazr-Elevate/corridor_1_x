import type { ReactNode } from "react";
import { TraderShell } from "@/components/shell/TraderShell";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return <TraderShell>{children}</TraderShell>;
}
