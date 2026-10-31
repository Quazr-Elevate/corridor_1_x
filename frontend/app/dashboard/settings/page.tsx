"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError, type Me, type SecurityOverview } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useMe } from "@/lib/useMe";
import { PASSPORT_PATH, formatDay, statusMeta } from "@/lib/verification";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { HoldButton, Segmented } from "@/components/ui/Controls";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { PasswordInput } from "@/components/auth/PasswordInput";
import { DISPLAY_CURRENCIES, isDisplayCurrency, useFx, type DisplayCurrency } from "@/components/fx/FxContext";
import { approxPrice, formatPrice, rateDateLabel, withApprox } from "@/components/products/format";
import { initials, memberCode } from "@/components/trader/format";

const MIN_PASSWORD = 8;

/**
 * Settings & security — password, display currency, sign-in activity, and account deletion, in the
 * Passport's language: relief sections on the left, who you're signed in
 * as on the right. Each section has its own action; anchors
 * (#password, #currency, #session, #delete-account) are deep-link targets.
 */
export default function SettingsPage() {
  const { me } = useMe();
  return (
    <div className="pt-6 sm:pt-10">
      <header className="animate-rise">
        <p className="t-label text-fg-3">Account</p>
        <h1 className="t-large mt-2 text-fg">Settings &amp; security</h1>
        <p className="t-callout mt-2 max-w-xl text-fg-2">How you sign in, and how to leave.</p>
      </header>

      <div className="mt-8 grid items-start gap-8 sm:mt-10 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Sections first in the DOM: on phones the password form leads. */}
        <div className="min-w-0 space-y-6 lg:col-start-1 lg:row-start-1">
          <PasswordSection />
          <CurrencySection />
          <SessionSection />
          <DangerSection />
        </div>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:col-start-2 lg:row-start-1">
          {me ? <SignedInCard me={me} /> : <Skeleton className="h-[280px] rounded-[26px]" />}
          <SectionNav />
        </aside>
      </div>
    </div>
  );
}

/* ───────────────────────────── Shared ───────────────────────────── */

const NAV: ReadonlyArray<{ id: string; label: string; icon: IconName }> = [
  { id: "password", label: "Password", icon: "key" },
  { id: "currency", label: "Display currency", icon: "globe" },
  { id: "session", label: "Sign-in & security", icon: "shield" },
  { id: "delete-account", label: "Delete account", icon: "trash" },
];

function SectionNav() {
  return (
    <nav aria-label="Settings sections" className="relief hidden rounded-[26px] p-2 lg:block">
      <p className="t-label px-3 pb-2 pt-2.5 text-fg-3">Sections</p>
      <ul className="space-y-0.5">
        {NAV.map((n, i) => (
          <li key={n.id}>
            <a
              href={`#${n.id}`}
              onClick={(e) => {
                const el = document.getElementById(n.id);
                if (!el) return;
                e.preventDefault();
                el.scrollIntoView({ behavior: "smooth", block: "start" });
                history.replaceState(null, "", `#${n.id}`);
              }}
              className="flex items-center gap-3 rounded-[16px] px-3 py-2.5 text-[14px] font-medium text-fg-3 transition-colors duration-300 hover:bg-fg/[0.05] hover:text-fg"
            >
              <span className="t-code text-[11px] text-fg-3">{String(i + 1).padStart(2, "0")}</span>
              <span className="min-w-0 flex-1 truncate">{n.label}</span>
              <Icon name={n.icon} size={15} className="shrink-0 text-fg-3" />
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Who you're signed in as — real account facts, nothing editable here. */
function SignedInCard({ me }: { me: Me }) {
  const meta = statusMeta(me.verification.status);
  return (
    <section aria-labelledby="signed-in-title" className="relief rounded-[26px] p-5">
      <h2 id="signed-in-title" className="t-label text-fg-3">
        Signed in as
      </h2>
      <div className="mt-4 flex items-center gap-3">
        <span className="solid t-code grid size-11 shrink-0 place-items-center rounded-full text-[12px]">
          {initials(me)}
        </span>
        <div className="min-w-0">
          <p className="t-headline truncate text-fg">{me.primary.fullName || "Your account"}</p>
          <p className="t-sub truncate text-fg-3">{me.email}</p>
        </div>
      </div>
      <dl className="mt-5 space-y-3 border-t border-line pt-4">
        <Fact label="Member ID">
          <span className="t-code text-fg">{memberCode(me.userId)}</span>
        </Fact>
        <Fact label="Email">
          {me.emailVerifiedAt ? (
            <span className="t-sub text-fg-2">Confirmed {formatDay(me.emailVerifiedAt)}</span>
          ) : (
            <Chip tone="move" size="sm" noIcon>
              Not confirmed
            </Chip>
          )}
        </Fact>
        <Fact label="Password">
          <span className="t-sub text-fg-2">Set by you</span>
        </Fact>
        <Fact label="Passport">
          <Link href={PASSPORT_PATH} className="rounded-full">
            <Chip tone={meta.tone} size="sm" icon={me.verification.status === "pending_verification" ? "clock" : undefined}>
              {meta.label}
            </Chip>
          </Link>
        </Fact>
      </dl>
    </section>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="t-label text-fg-3">{label}</dt>
      <dd className="min-w-0 text-right">{children}</dd>
    </div>
  );
}

function SectionCard({
  id,
  index,
  icon,
  title,
  description,
  tone,
  children,
}: {
  id: string;
  index: string;
  icon: IconName;
  title: string;
  description: ReactNode;
  tone?: "danger";
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className={cn(
        "relief scroll-mt-32 rounded-[30px] p-5 sm:p-8",
        tone === "danger" && "[box-shadow:var(--relief),inset_0_0_0_1px_rgb(179_38_30/0.18)]",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="t-label text-fg-3">{index}</p>
          <h2 id={`${id}-title`} className={cn("t-title2 mt-1.5", tone === "danger" ? "text-danger" : "text-fg")}>
            {title}
          </h2>
          <div className="t-callout mt-1.5 max-w-xl text-fg-2">{description}</div>
        </div>
        <span
          aria-hidden="true"
          className={cn(
            "grid size-12 shrink-0 place-items-center rounded-full",
            tone === "danger" ? "bg-danger-soft text-danger" : "well text-fg-2",
          )}
        >
          <Icon name={icon} size={20} />
        </span>
      </div>
      <div className="mt-6 border-t border-line pt-6 sm:mt-7 sm:pt-7">{children}</div>
    </section>
  );
}

/* ──────────────────────────── Password ──────────────────────────── */

function PasswordSection() {
  const { me, refetch } = useMe();
  const toast = useToast();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ current?: string; next?: string; confirm?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setFormError(null);

    const fe: typeof errors = {};
    if (!current) fe.current = "Enter your current password.";
    if (next.length < MIN_PASSWORD) fe.next = `Use at least ${MIN_PASSWORD} characters.`;
    else if (next === current) fe.next = "Pick a password different from your current one.";
    if (!fe.next && next !== confirm) fe.confirm = "Passwords don’t match.";
    setErrors(fe);
    if (Object.keys(fe).length) return;

    setSubmitting(true);
    try {
      await api.changePassword({ currentPassword: current, newPassword: next });
      setCurrent("");
      setNext("");
      setConfirm("");
      toast("Password updated", "verified");
      await refetch();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setErrors({ current: "That isn’t your current password." });
      } else if (err instanceof ApiError && err.status === 400) {
        setErrors({ next: err.message });
      } else if (err instanceof ApiError && err.status === 429) {
        setFormError("Too many attempts. Wait a minute, then try again.");
      } else {
        setFormError(err instanceof Error ? err.message : "Couldn’t update your password. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SectionCard
      id="password"
      index="01"
      icon="key"
      title="Password"
      description="Changing it signs you out on every other device."
    >

      <form onSubmit={onSubmit} noValidate className="space-y-5">
        {/* Helps password managers pair the new password with this account. */}
        {me?.email ? (
          <input type="email" name="username" autoComplete="username" value={me.email} readOnly hidden />
        ) : null}

        <PasswordInput
          label="Current password"
          name="current-password"
          autoComplete="current-password"
          required
          error={errors.current}
          value={current}
          onChange={(e) => {
            setCurrent(e.target.value);
            if (errors.current) setErrors((x) => ({ ...x, current: undefined }));
          }}
        />

        <div className="grid gap-5 sm:grid-cols-2 sm:gap-4">
          <PasswordInput
            label="New password"
            name="new-password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD}
            hint={`At least ${MIN_PASSWORD} characters.`}
            error={errors.next}
            value={next}
            onChange={(e) => {
              setNext(e.target.value);
              if (errors.next) setErrors((x) => ({ ...x, next: undefined }));
            }}
          />
          <PasswordInput
            label="Confirm new password"
            name="confirm-password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD}
            error={errors.confirm}
            value={confirm}
            onChange={(e) => {
              setConfirm(e.target.value);
              if (errors.confirm) setErrors((x) => ({ ...x, confirm: undefined }));
            }}
          />
        </div>

        {formError ? <Notice tone="frozen">{formError}</Notice> : null}

        <div className="flex justify-end pt-1">
          <Button type="submit" loading={submitting} icon="lock" className="w-full sm:w-auto">
            Update password
          </Button>
        </div>
      </form>
    </SectionCard>
  );
}

/* ───────────────────────── Display currency ─────────────────────── */

const CURRENCY_LABEL: Record<DisplayCurrency, string> = {
  INR: "₹ INR",
  AED: "AED",
  USD: "$ USD",
};

function CurrencySection() {
  const { me, refetch } = useMe();
  const { rates } = useFx();
  const toast = useToast();
  const saved = isDisplayCurrency(me?.displayCurrency) ? (me!.displayCurrency.toUpperCase() as DisplayCurrency) : null;
  const [value, setValue] = useState<DisplayCurrency | null>(saved);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setValue(saved), [saved]);

  async function choose(next: DisplayCurrency) {
    if (saving || next === value) return;
    const prev = value;
    setValue(next);
    setError(null);
    setSaving(true);
    try {
      await api.updateMe({ displayCurrency: next });
      await refetch();
      toast(`Prices now convert to ${next}`, "verified");
    } catch (err) {
      setValue(prev);
      setError(err instanceof Error ? err.message : "Couldn’t save your display currency. Try again.");
    } finally {
      setSaving(false);
    }
  }

  // A worked example from live rates: a lot priced in another currency.
  const [amount, from] = value === "AED" ? [42000, "INR"] : [520, "AED"];
  const sample = value ? approxPrice(amount, from, value, rates) : null;
  const date = rateDateLabel(rates?.asOf);

  return (
    <SectionCard
      id="currency"
      index="02"
      icon="globe"
      title="Display currency"
      description="Lots keep the seller’s own price. When it’s in another currency, an indicative conversion follows it, and you type market price filters in this currency."
    >
      <div className="space-y-4">
        {value ? (
          <Segmented
            label="Display currency"
            value={value}
            onChange={choose}
            options={DISPLAY_CURRENCIES.map((c) => ({ value: c, label: CURRENCY_LABEL[c] }))}
          />
        ) : (
          <Skeleton className="h-11 w-64 rounded-full" />
        )}
        {sample && value ? (
          <p className="t-sub text-fg-3" aria-live="polite">
            For example {withApprox(formatPrice(amount, "MT", from), sample)}
            {date ? <> — indicative, rate of {date}</> : null}
          </p>
        ) : null}
        {error ? <Notice tone="frozen">{error}</Notice> : null}
      </div>
    </SectionCard>
  );
}

/* ───────────────────────────── Session ──────────────────────────── */

const EVENT_LABEL: Record<string, string> = {
  login_succeeded: "Signed in",
  login_failed: "Wrong password",
  locked: "Locked after failed attempts",
  locked_support: "Locked — support must unlock",
  unlocked: "Unlocked by support",
  session_replaced: "Signed out by a sign-in elsewhere",
  sessions_revoked: "Signed out everywhere",
  password_changed: "Password changed",
  password_reset: "Password reset",
};

/** "Chrome on macOS" from a user-agent string — enough to recognise a device. */
function deviceName(ua: string | null): string {
  if (!ua) return "Unknown device";
  const browser = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox"
    : /Safari\//.test(ua) ? "Safari" : "Browser";
  const os = /iPhone|iPad/.test(ua) ? "iOS" : /Android/.test(ua) ? "Android" : /Mac OS X/.test(ua) ? "macOS"
    : /Windows/.test(ua) ? "Windows" : /Linux/.test(ua) ? "Linux" : "";
  return os ? `${browser} on ${os}` : browser;
}

function when(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

function SessionSection() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [overview, setOverview] = useState<SecurityOverview | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let alive = true;
    api
      .security()
      .then((o) => alive && setOverview(o))
      .catch(() => alive && setLoadError(true));
    return () => {
      alive = false;
    };
  }, []);

  async function signOut() {
    setBusy(true);
    try {
      await api.logout();
    } catch {
      // The session may already be gone — leave either way.
    } finally {
      router.replace("/login");
    }
  }

  const device = overview?.device;
  return (
    <SectionCard
      id="session"
      index="03"
      icon="shield"
      title="Sign-in & security"
      description={
        <>
          One device at a time: signing in somewhere else signs this device out. Sessions end after{" "}
          {overview ? Math.round(overview.idleTimeoutMinutes / 60) : 12} hours without activity, and after{" "}
          {overview?.maxSessionDays ?? 7} days in any case.
        </>
      }
    >
      <div className="space-y-6">
        {device ? (
          <div className="well flex items-start gap-4 rounded-[22px] p-4">
            <span aria-hidden="true" className="grid size-10 shrink-0 place-items-center rounded-full bg-lime-soft text-accent">
              <Icon name="globe" size={18} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="t-body font-medium text-fg">
                {deviceName(device.userAgent)} <Chip tone="verified" size="sm" noIcon>This device</Chip>
              </p>
              <p className="t-sub mt-1 text-fg-3">
                Signed in {when(device.createdAt)} · last active {when(device.lastSeenAt)}
                {device.ipPrefix ? <> · network {device.ipPrefix}</> : null}
              </p>
            </div>
          </div>
        ) : loadError ? (
          <Notice tone="frozen">Couldn’t load your sign-in activity.</Notice>
        ) : (
          <Skeleton className="h-[76px] rounded-[22px]" />
        )}

        {overview && overview.recent.length ? (
          <div>
            <p className="t-label text-fg-3">Recent activity</p>
            <ul className="mt-3 divide-y divide-line">
              {overview.recent.slice(0, 8).map((e, i) => (
                <li key={`${e.createdAt}-${i}`} className="flex items-center justify-between gap-3 py-2.5">
                  <span className={cn("t-sub", e.event.startsWith("lock") || e.event === "login_failed" ? "text-danger" : "text-fg")}>
                    {EVENT_LABEL[e.event] ?? e.event}
                    {e.userAgent ? <span className="text-fg-3"> · {deviceName(e.userAgent)}</span> : null}
                  </span>
                  <span className="t-code shrink-0 text-fg-3">{when(e.createdAt)}</span>
                </li>
              ))}
            </ul>
            <p className="t-sub mt-3 text-fg-3">
              Don’t recognise something? Change your password above, then contact support.
            </p>
          </div>
        ) : null}

        <Button variant="secondary" icon="logout" loading={busy} onClick={signOut} className="w-full sm:w-auto">
          Sign out
        </Button>
      </div>
    </SectionCard>
  );
}

/* ─────────────────────────── Danger zone ────────────────────────── */

function DangerSection() {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function deleteAccount() {
    setError(null);
    setDeleting(true);
    try {
      await api.deleteMe();
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn’t delete your account. Try again.");
      setDeleting(false);
    }
  }

  return (
    <SectionCard
      id="delete-account"
      index="04"
      icon="trash"
      tone="danger"
      title="Delete account"
      description={
        <>
          Your profile is erased right away and you’re signed out. Under India’s DPDP Act, business,
          product and payout records may be kept for up to 7 years for tax compliance, hidden from
          everyone except audit. This can’t be undone.
        </>
      }
    >
      <div className="space-y-4">
        <HoldButton tone="danger" icon="trash" loading={deleting} onCommit={deleteAccount} className="w-full sm:w-auto">
          Delete my account
        </HoldButton>
        <p className="t-sub text-fg-3">Press and hold to confirm.</p>
        {error ? <Notice tone="frozen">{error}</Notice> : null}
      </div>
    </SectionCard>
  );
}
