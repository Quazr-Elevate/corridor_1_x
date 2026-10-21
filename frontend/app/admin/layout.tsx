"use client";

import { usePathname } from "next/navigation";
import { TowerShell } from "@/components/shell/TowerShell";

/**
 * Ops (Control Tower) layout — the shell mounts once and stays mounted
 * across admin routes. /admin/login is the gate and renders bare.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/admin/login") return <>{children}</>;
  return <TowerShell>{children}</TowerShell>;
}
