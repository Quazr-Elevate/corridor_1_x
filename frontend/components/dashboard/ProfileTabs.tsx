"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { useUnsavedGuard } from "@/lib/useUnsavedGuard";

const TABS = [
  { href: "/dashboard/profile/primary", label: "Primary details", key: "primary" as const },
  { href: "/dashboard/profile/business", label: "Business details", key: "business" as const },
  { href: "/dashboard/profile/bank", label: "Bank details", key: "bank" as const },
];

export function ProfileTabs() {
  const pathname = usePathname();
  const router = useRouter();
  const { confirmIfDirty } = useUnsavedGuard();

  return (
    <nav
      role="tablist"
      aria-label="Profile sections"
      className="no-scrollbar overflow-x-auto border-b border-line-soft"
    >
      <div className="flex min-w-full gap-6">
        {TABS.map((t) => {
          const active =
            pathname === t.href ||
            (pathname === "/dashboard/profile" && t.key === "primary");
          return (
            <Link
              key={t.href}
              href={t.href}
              role="tab"
              aria-selected={active}
              onClick={(e) => {
                if (active) return;
                e.preventDefault();
                confirmIfDirty(() => router.push(t.href));
              }}
              className={cn(
                "relative flex items-center gap-2 whitespace-nowrap px-1 py-3 text-[13px] font-medium transition-colors",
                active ? "text-paper" : "text-paper-muted hover:text-paper",
              )}
            >
              <span>{t.label}</span>
              {active ? (
                <span
                  aria-hidden
                  className="absolute inset-x-0 -bottom-px h-[2px] rounded-t bg-accent"
                />
              ) : null}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
