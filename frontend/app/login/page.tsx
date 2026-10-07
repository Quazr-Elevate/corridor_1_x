"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, storeUserId } from "@/lib/api";
import { AuthButton, AuthCard, AuthField, AuthInput } from "@/components/auth/AuthCard";

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const nextTarget = params.get("next") || "/dashboard";
  const verified = params.get("verified") === "1";
  const magicInvalid = params.get("magic") === "invalid";
  const fromMagic = params.get("from") === "magic";
  const prefillEmail = params.get("email") ?? "";

  const [email, setEmail] = useState(prefillEmail);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.login({
        email: email.trim().toLowerCase(),
        password,
      });
      storeUserId(res.userId);
      // Temp-password login lands in the dashboard like any other
      // login — the user is nudged (not forced) to swap the credential
      // for a real password under Settings → Security &amp; Privacy.
      router.replace(nextTarget);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Welcome back"
      subtitle="Sign in with your work email."
      footer={
        <>
          New to Cor1x?{" "}
          <Link href="/signup" className="text-accent hover:text-accent-hover underline">
            Create an account
          </Link>
        </>
      }
    >
      {verified && (
        <div className="mb-4 rounded-lg border border-lime-500/40 bg-lime-500/10 p-3 text-sm text-lime-200">
          Email verified. Please log in to continue.
        </div>
      )}
      {magicInvalid && (
        <div className="mb-4 rounded-lg border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
          That magic link is invalid or expired. Type the temp password from
          the email, or request a new one.
        </div>
      )}
      {fromMagic && (
        <div className="mb-4 rounded-lg border border-accent/30 bg-accent/10 p-3 text-sm text-paper">
          Paste the temporary password from the welcome email. You can set a
          real password after signing in, under <strong>Settings → Security
          &amp; Privacy</strong>.
        </div>
      )}
      <form onSubmit={onSubmit} className="space-y-4">
        <AuthField label="Work email">
          <AuthInput
            type="email"
            autoComplete="email"
            required
            placeholder="you@yourcompany.in"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </AuthField>
        <AuthField label="Password">
          <div className="relative">
            <AuthInput
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="pr-11"
            />
            <EyeToggle on={showPassword} onClick={() => setShowPassword((v) => !v)} />
          </div>
        </AuthField>
        {error && (
          <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200">
            {error}
          </div>
        )}
        <AuthButton type="submit" loading={submitting}>
          Log in
        </AuthButton>
      </form>
    </AuthCard>
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
      {on ? (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a19.4 19.4 0 0 1 4.05-5.47" />
          <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a19.5 19.5 0 0 1-3.16 4.16" />
          <path d="M9.88 9.88a3 3 0 0 0 4.24 4.24" />
          <line x1="1" y1="1" x2="23" y2="23" />
        </svg>
      ) : (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      )}
    </button>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <AuthCard title="Loading…">
          <div className="py-6" />
        </AuthCard>
      }
    >
      <LoginInner />
    </Suspense>
  );
}
