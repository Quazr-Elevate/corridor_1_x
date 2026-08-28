"use client";

import { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CheckSquare, LayoutDashboard, LogOut, ShieldCheck, Users } from "lucide-react";
import { cn } from "@/lib/cn";
import { adminApi } from "@/lib/adminApi";
import { UnsavedGuardProvider, useUnsavedGuard } from "@/lib/useUnsavedGuard";

interface Props {
  children: ReactNode;
}

export function AdminShell({ children }: Props) {
  return (
    <UnsavedGuardProvider>
      <AdminShellInner>{children}</AdminShellInner>
    </UnsavedGuardProvider>
  );
}

function AdminShellInner({ children }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const { confirmIfDirty } = useUnsavedGuard();
  const [email, setEmail] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    adminApi
      .me()
      .then((r) => setEmail(r.email))
      .catch(() => router.replace("/admin/login"))
      .finally(() => setReady(true));
  }, [router]);

  const signOut = async () => {
    confirmIfDirty(async () => {
      try {
        await adminApi.logout();
      } finally {
        router.replace("/admin/login");
      }
    });
  };

  if (!ready) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-ink text-paper-muted">
        <p className="text-sm">Loading…</p>
      </main>
    );
  }
  if (!email) return null;

  return (
    <div className="min-h-screen bg-ink text-paper">
      <div className="mx-auto flex max-w-7xl">
        <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col border-r border-line-soft/60 px-4 py-6 md:flex">
          <GuardedLink
            href="/admin"
            className="mb-8 flex items-center gap-2"
            confirmIfDirty={confirmIfDirty}
          >
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-line-soft bg-ink-elevated">
              <ShieldCheck className="h-4 w-4 text-accent" aria-hidden />
            </span>
            <div>
              <p className="text-[10px] uppercase tracking-widest text-paper-muted">
                Cor1x
              </p>
              <p className="text-sm font-semibold tracking-tight text-paper">
                Admin
              </p>
            </div>
          </GuardedLink>

          <nav className="space-y-1">
            <NavItem
              href="/admin"
              icon={LayoutDashboard}
              label="Dashboard"
              active={pathname === "/admin"}
              confirmIfDirty={confirmIfDirty}
            />
            <NavItem
              href="/admin/verify"
              icon={CheckSquare}
              label="Verify queue"
              active={pathname.startsWith("/admin/verify")}
              confirmIfDirty={confirmIfDirty}
            />
            <NavItem
              href="/admin/users"
              icon={Users}
              label="Users"
              active={pathname.startsWith("/admin/users")}
              confirmIfDirty={confirmIfDirty}
            />
          </nav>

          <div className="mt-auto border-t border-line-soft/60 pt-4">
            <p className="truncate text-[11px] text-paper-muted">Signed in as</p>
            <p className="truncate text-xs font-medium text-paper">{email}</p>
            <button
              type="button"
              onClick={signOut}
              className="mt-3 inline-flex items-center gap-2 text-xs text-paper-muted transition-colors hover:text-paper"
            >
              <LogOut aria-hidden className="h-3.5 w-3.5" />
              Sign out
            </button>
          </div>
        </aside>

        <main className="min-w-0 flex-1 p-5 sm:p-8">{children}</main>
      </div>
    </div>
  );
}

function GuardedLink({
  href,
  className,
  confirmIfDirty,
  children,
}: {
  href: string;
  className?: string;
  confirmIfDirty: (nav: () => void) => boolean;
  children: ReactNode;
}) {
  const router = useRouter();
  return (
    <Link
      href={href}
      className={className}
      onClick={(e) => {
        e.preventDefault();
        confirmIfDirty(() => router.push(href));
      }}
    >
      {children}
    </Link>
  );
}

function NavItem({
  href,
  icon: Icon,
  label,
  active,
  confirmIfDirty,
}: {
  href: string;
  icon: typeof Users;
  label: string;
  active?: boolean;
  confirmIfDirty: (nav: () => void) => boolean;
}) {
  return (
    <GuardedLink
      href={href}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-colors",
        active
          ? "bg-accent-soft text-paper"
          : "text-paper-muted hover:bg-ink-elevated hover:text-paper",
      )}
      confirmIfDirty={confirmIfDirty}
    >
      <Icon
        aria-hidden
        className={cn("h-4 w-4", active ? "text-accent" : "text-paper-muted")}
      />
      {label}
    </GuardedLink>
  );
}
