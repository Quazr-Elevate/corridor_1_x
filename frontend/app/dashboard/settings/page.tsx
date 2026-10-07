"use client";

import { useState } from "react";
import { AlertTriangle, LockKeyhole, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { AuthButton, AuthField, AuthInput } from "@/components/auth/AuthCard";

/**
 * Settings — a single page split into labelled sections, each one a
 * self-contained form. New sections (notifications, data export, soft
 * delete) will slot in below ``Security &amp; Privacy`` the same way.
 */
export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header>
        <p className="text-[10px] uppercase tracking-widest text-paper-muted">
          Account
        </p>
        <h1 className="mt-2 text-display text-paper">Settings</h1>
        <p className="mt-2 text-sm text-paper-muted">
          Manage how you sign in and how Cor1x reaches you.
        </p>
      </header>

      <SecurityPrivacySection />
    </div>
  );
}

// ─── Security & privacy ─────────────────────────────────────────────

function SecurityPrivacySection() {
  const { me, refetch } = useMe();

  // ``firstTime`` means the active session was issued via the temp
  // credential — the user hasn't picked a real password yet. We hide
  // the "current password" field in that mode (session cookie is
  // already proof of identity) and show a warning banner at the top of
  // the section so it reads as an action item, not a chore.
  const firstTime = Boolean(me?.mustChangePassword);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const justSaved = savedAt != null && Date.now() - savedAt < 4000;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (!firstTime && newPassword === currentPassword) {
      setError("New password must be different from the current one.");
      return;
    }
    setSubmitting(true);
    try {
      await api.changePassword({
        currentPassword: firstTime ? "" : currentPassword,
        newPassword,
      });
      await refetch();
      setCurrentPassword("");
      setNewPassword("");
      setConfirm("");
      setSavedAt(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-card border border-line-soft bg-ink-soft/70 p-6 md:p-8 space-y-5">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-field bg-accent/10 text-accent">
          <ShieldCheck className="h-5 w-5" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-title text-paper">Security &amp; Privacy</h2>
          <p className="mt-1 text-sm text-paper-muted">
            Rotate your password here. Treat it like your email password —
            Cor1x will never ask you for it over chat or email.
          </p>
        </div>
      </div>

      {firstTime && (
        <div className="flex items-start gap-3 rounded-field border border-amber-400/30 bg-amber-400/5 p-3">
          <AlertTriangle
            className="mt-0.5 h-4 w-4 shrink-0 text-amber-400"
            aria-hidden
          />
          <div className="min-w-0 flex-1 text-xs text-paper leading-relaxed">
            <p className="font-semibold text-amber-400">
              You&apos;re using a temporary password
            </p>
            <p className="mt-0.5 text-paper-muted">
              Pick a real password to use from now on. The temp password from
              the welcome email will stop working once you save a new one.
            </p>
          </div>
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-4">
        {!firstTime && (
          <AuthField label="Current password">
            <div className="relative">
              <AuthInput
                type={showCurrent ? "text" : "password"}
                autoComplete="current-password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Your current password"
                className="pr-11"
              />
              <EyeToggle
                on={showCurrent}
                onClick={() => setShowCurrent((v) => !v)}
              />
            </div>
          </AuthField>
        )}

        <AuthField label="New password" hint="At least 8 characters.">
          <div className="relative">
            <AuthInput
              type={showNew ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Pick a password you'll remember"
              className="pr-11"
            />
            <EyeToggle on={showNew} onClick={() => setShowNew((v) => !v)} />
          </div>
        </AuthField>

        <AuthField label="Confirm new password">
          <AuthInput
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Type the new password again"
          />
        </AuthField>

        {error && (
          <div className="rounded-field border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <AuthButton
            type="submit"
            loading={submitting}
            className="sm:w-auto sm:px-6"
          >
            <span className="inline-flex items-center gap-2">
              <LockKeyhole className="h-4 w-4" aria-hidden /> Update password
            </span>
          </AuthButton>
          {justSaved && (
            <span className="text-xs text-accent">Password updated ✓</span>
          )}
        </div>
      </form>
    </section>
  );
}

function EyeToggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={on ? "Hide password" : "Show password"}
      className="absolute right-3 top-1/2 -translate-y-1/2 text-paper-muted hover:text-paper transition"
      tabIndex={-1}
    >
      {on ? "🙈" : "👁"}
    </button>
  );
}
