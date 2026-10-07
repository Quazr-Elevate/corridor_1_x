"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  LogOut,
  Settings as SettingsIcon,
  UserRound,
  X,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { useUnsavedGuard } from "@/lib/useUnsavedGuard";

interface Props {
  open: boolean;
  onClose: () => void;
  email: string;
  businessName?: string | null;
  fullName?: string | null;
  onSignOut: () => void;
}

export function Drawer({ open, onClose, email, businessName, fullName, onSignOut }: Props) {
  const pathname = usePathname();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div
        aria-hidden
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-line-soft bg-ink-soft/95 backdrop-blur-xl"
      >
        <div className="flex items-start justify-between px-5 pt-6">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-paper-muted">
              <span
                aria-hidden
                className="mr-1.5 inline-block h-1 w-1 -translate-y-[2px] rounded-full bg-accent align-middle"
              />
              Cor1x
            </p>
            <p className="mt-1 text-lg font-extrabold tracking-[-0.03em] text-paper">
              Menu
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="rounded-full p-1.5 text-paper-muted transition-colors hover:bg-ink-elevated hover:text-paper"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav
          className="mt-6 flex flex-1 flex-col px-3"
          aria-label="Primary navigation"
        >
          {/* Primary destinations — the two things people come here for. */}
          <div className="space-y-1">
            <NavItem
              href="/dashboard"
              icon={LayoutDashboard}
              label="Dashboard"
              active={pathname === "/dashboard"}
              onNavigate={onClose}
            />
            <NavItem
              href="/dashboard/account"
              icon={UserRound}
              label="My Account"
              active={pathname.startsWith("/dashboard/account")}
              onNavigate={onClose}
            />
          </div>

          {/* Settings sits at the bottom of the nav — a "chore" link,
              reached when the user wants to tune something rather than
              get work done. mt-auto pushes it down. */}
          <div className="mt-auto space-y-1 pb-2">
            <NavItem
              href="/dashboard/settings"
              icon={SettingsIcon}
              label="Settings"
              active={pathname.startsWith("/dashboard/settings")}
              onNavigate={onClose}
            />
          </div>
        </nav>

        <div className="border-t border-line-soft p-4">
          <p className="truncate text-[11px] text-paper-muted">Signed in as</p>
          <p className="truncate text-sm font-medium text-paper">
            {fullName || businessName || email}
          </p>
          <p className="truncate text-xs text-paper-muted">{email}</p>
          <button
            type="button"
            onClick={onSignOut}
            className="mt-3 inline-flex items-center gap-2 text-xs text-paper-muted transition-colors hover:text-paper"
          >
            <LogOut aria-hidden className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </aside>
    </>
  );
}

function NavItem({
  href,
  icon: Icon,
  label,
  active,
  onNavigate,
}: {
  href: string;
  icon: LucideIcon;
  label: string;
  active?: boolean;
  onNavigate?: () => void;
}) {
  const router = useRouter();
  const { confirmIfDirty } = useUnsavedGuard();

  return (
    <Link
      href={href}
      onClick={(e) => {
        e.preventDefault();
        confirmIfDirty(() => {
          onNavigate?.();
          router.push(href);
        });
      }}
    >
      <div
        className={cn(
          "group flex items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-colors",
          active
            ? "bg-accent-soft text-paper"
            : "text-paper-muted hover:bg-ink-elevated hover:text-paper",
        )}
      >
        <Icon
          aria-hidden
          className={cn(
            "h-4 w-4 shrink-0",
            active ? "text-accent" : "text-paper-muted group-hover:text-paper",
          )}
        />
        <span className="flex-1 truncate">{label}</span>
      </div>
    </Link>
  );
}
