"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Check,
  LayoutDashboard,
  Lock,
  LogOut,
  Package,
  ShieldCheck,
  UserRound,
  X,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import type { Completion } from "@/lib/api";
import { useUnsavedGuard } from "@/lib/useUnsavedGuard";

interface Props {
  open: boolean;
  onClose: () => void;
  status?: string;
  completion?: Completion;
  mobile: string;
  fullName?: string | null;
  onSignOut: () => void;
}

export function Drawer({
  open,
  onClose,
  status,
  completion,
  mobile,
  fullName,
  onSignOut,
}: Props) {
  const pathname = usePathname();
  const productsUnlocked = status === "verified";

  const profileComplete =
    !!completion?.primary && !!completion?.business && !!completion?.bank;

  // Escape key + body scroll lock while open.
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
      {/* Backdrop */}
      <div
        aria-hidden
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
      />
      {/* Drawer panel */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-line-soft bg-ink-soft/95 backdrop-blur-xl"
      >
        {/* Header */}
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
              Dashboard
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

        {/* Nav */}
        <nav className="mt-6 flex-1 space-y-1 px-3">
          <NavItem
            href="/dashboard"
            icon={LayoutDashboard}
            label="Dashboard"
            active={pathname === "/dashboard"}
            onNavigate={onClose}
          />
          <NavItem
            href="/dashboard/profile"
            icon={UserRound}
            label="Profile"
            active={pathname.startsWith("/dashboard/profile")}
            done={profileComplete}
            onNavigate={onClose}
          />
          <NavItem
            href="/dashboard/trust-score"
            icon={ShieldCheck}
            label="Trust score"
            active={pathname.startsWith("/dashboard/trust-score")}
            done={completion?.seller}
            optional
            onNavigate={onClose}
          />
          <NavItem
            href={productsUnlocked ? "/dashboard/products" : "#"}
            icon={Package}
            label="Product"
            active={pathname.startsWith("/dashboard/products")}
            locked={!productsUnlocked}
            onNavigate={onClose}
          />
          {!productsUnlocked ? (
            <p className="ml-11 pr-3 pt-1 text-[10px] leading-snug text-paper-muted/60">
              Unlocks once you&apos;re verified
            </p>
          ) : null}
        </nav>

        {/* User footer */}
        <div className="border-t border-line-soft p-4">
          <p className="truncate text-[11px] text-paper-muted">Signed in as</p>
          <p className="truncate text-sm font-medium text-paper">
            {fullName ? fullName : `+91 ${mobile.slice(0, 5)} ${mobile.slice(5)}`}
          </p>
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
  done,
  optional,
  locked,
  onNavigate,
}: {
  href: string;
  icon: LucideIcon;
  label: string;
  active?: boolean;
  done?: boolean;
  optional?: boolean;
  locked?: boolean;
  onNavigate?: () => void;
}) {
  const inner = (
    <div
      className={cn(
        "group flex items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-colors",
        active
          ? "bg-accent-soft text-paper"
          : "text-paper-muted hover:bg-ink-elevated hover:text-paper",
        locked && "cursor-not-allowed opacity-50 hover:bg-transparent hover:text-paper-muted",
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
      {locked ? <Lock aria-hidden className="h-3 w-3 text-paper-muted/60" /> : null}
      {done ? (
        <span
          aria-hidden
          className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-accent text-accent-fg"
        >
          <Check className="h-2.5 w-2.5" strokeWidth={3} />
        </span>
      ) : optional && !done ? (
        <span className="text-[9px] uppercase tracking-widest text-paper-muted/50">
          Opt
        </span>
      ) : null}
    </div>
  );

  const router = useRouter();
  const { confirmIfDirty } = useUnsavedGuard();

  if (locked) return <div>{inner}</div>;
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
      {inner}
    </Link>
  );
}
