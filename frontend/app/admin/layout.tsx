"use client";

import { usePathname } from "next/navigation";
import { AdminShell } from "@/components/admin/AdminShell";

/**
 * Admin layout — mounts AdminShell ONCE and keeps it mounted across every
 * admin route. Next swaps only the page body (children) on navigation, so
 * the sidebar, auth check, theme, and ambient field never remount — no more
 * flicker between pages. The RouteTransition inside AdminShell animates the
 * body on each pathname change.
 *
 * /admin/login is the exception: it has no shell (it's the gate), so it
 * renders bare.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/admin/login") return <>{children}</>;
  return <AdminShell>{children}</AdminShell>;
}
