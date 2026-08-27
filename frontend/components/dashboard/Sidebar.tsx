"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Building2,
  Check,
  Landmark,
  LayoutDashboard,
  Lock,
  LogOut,
  Package,
  UserRound,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import type { Completion } from "@/lib/api";

interface Props {
  completion?: Completion;
  status?: string;
  onSignOut: () => void;
  mobile: string;
}

export function Sidebar({ completion, status, onSignOut, mobile }: Props) {
  const pathname = usePathname();
  const productsUnlocked = status === "verified";

  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-line-soft bg-ink-soft/60 backdrop-blur-md">
      <div className="px-5 pt-6">
        <p className="text-[10px] uppercase tracking-widest text-paper-muted">
          <span aria-hidden className="mr-1.5 inline-block h-1 w-1 translate-y-[-2px] rounded-full bg-accent align-middle" />
          Cor1x
        </p>
        <p className="mt-1 text-lg font-extrabold tracking-[-0.03em] text-paper">
          Dashboard
        </p>
      </div>

      <nav className="mt-6 flex-1 space-y-1 px-3">
        <NavItem
          href="/dashboard"
          icon={LayoutDashboard}
          label="Dashboard"
          active={pathname === "/dashboard"}
        />

        <div className="pt-3">
          <p className="px-3 pb-1 text-[10px] uppercase tracking-widest text-paper-muted/60">
            Profile
          </p>
          <NavItem
            href="/dashboard/profile/primary"
            icon={UserRound}
            label="Primary details"
            active={pathname === "/dashboard/profile/primary"}
            done={completion?.primary}
          />
          <NavItem
            href="/dashboard/profile/business"
            icon={Building2}
            label="Business details"
            active={pathname === "/dashboard/profile/business"}
            done={completion?.business}
          />
          <NavItem
            href="/dashboard/profile/bank"
            icon={Wallet}
            label="Bank details"
            active={pathname === "/dashboard/profile/bank"}
            done={completion?.bank}
          />
          <NavItem
            href="/dashboard/profile/seller"
            icon={Landmark}
            label="Seller details"
            active={pathname === "/dashboard/profile/seller"}
            done={completion?.seller}
            optional
          />
        </div>

        <div className="pt-3">
          <NavItem
            href={productsUnlocked ? "/dashboard/products" : "#"}
            icon={Package}
            label="Add product"
            active={pathname.startsWith("/dashboard/products")}
            locked={!productsUnlocked}
          />
          {!productsUnlocked ? (
            <p className="ml-11 pr-3 text-[10px] leading-snug text-paper-muted/60">
              Unlocks once you&apos;re verified
            </p>
          ) : null}
        </div>
      </nav>

      <div className="border-t border-line-soft p-4">
        <p className="truncate text-[11px] text-paper-muted">Signed in as</p>
        <p className="truncate text-sm font-medium text-paper">
          +91 {mobile.slice(0, 5)} {mobile.slice(5)}
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
}: {
  href: string;
  icon: LucideIcon;
  label: string;
  active?: boolean;
  done?: boolean;
  optional?: boolean;
  locked?: boolean;
}) {
  const content = (
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

  if (locked) {
    return <div>{content}</div>;
  }
  return <Link href={href}>{content}</Link>;
}
