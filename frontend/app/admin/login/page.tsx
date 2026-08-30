"use client";

import { FormEvent, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { ArrowRight, Eye, EyeOff, Lock } from "lucide-react";
import { adminApi } from "@/lib/adminApi";
import { Rise, SpatialField, useAdminTheme } from "@/components/admin/spatial";

export default function AdminLoginPage() {
  const router = useRouter();
  const { cls } = useAdminTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await adminApi.login(email.trim(), password);
      router.replace("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    background: "var(--sp-surface)",
    border: "1px solid var(--sp-border)",
    color: "var(--sp-text)",
  };

  return (
    <main
      className={cls + " relative flex min-h-dvh items-center justify-center overflow-hidden px-5"}
      style={{ paddingTop: "max(env(safe-area-inset-top),24px)", paddingBottom: "max(env(safe-area-inset-bottom),24px)" }}
    >
      <SpatialField />

      <div className="relative w-full max-w-[380px]">
        <Rise i={0} className="mb-8 flex flex-col items-center text-center">
          <span
            className="flex h-12 w-12 items-center justify-center rounded-[14px]"
            style={{ background: "var(--sp-lime-10)", boxShadow: "inset 0 0 0 1px var(--sp-lime-14)" }}
          >
            <Image src="/brand/x-mark-lime.svg" alt="" width={26} height={26} className="h-[26px] w-[26px]" />
          </span>
          <p className="mt-5 text-[10px] font-bold uppercase tracking-[0.18em]" style={{ color: "var(--sp-text-3)" }}>
            Corridor One X · Admin console
          </p>
          <h1 className="mt-2.5 text-[28px] font-semibold tracking-[-0.02em]" style={{ color: "var(--sp-text)" }}>
            Operator sign in
          </h1>
          <p className="mt-2 text-[13.5px]" style={{ color: "var(--sp-text-2)" }}>
            Restricted to authorized operators.
          </p>
        </Rise>

        <Rise i={1}>
          <form
            onSubmit={handleSubmit}
            className="sp-surface-2 flex flex-col gap-5 p-6"
            noValidate
          >
            <div>
              <label htmlFor="admin-email" className="mb-2 block text-[11px] font-bold uppercase tracking-[0.1em]" style={{ color: "var(--sp-text-3)" }}>
                Email
              </label>
              <input
                id="admin-email"
                type="email"
                placeholder="admin@cor1x.local"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-11 w-full rounded-[10px] px-3.5 text-[15px] outline-none transition-[border-color,box-shadow] duration-200 placeholder:opacity-50 focus:shadow-[0_0_0_3px_var(--sp-lime-18)]"
                style={inputStyle}
                onFocus={(e) => (e.currentTarget.style.borderColor = "var(--sp-lime)")}
                onBlur={(e) => (e.currentTarget.style.borderColor = "var(--sp-border)")}
              />
            </div>

            <div>
              <label htmlFor="admin-password" className="mb-2 block text-[11px] font-bold uppercase tracking-[0.1em]" style={{ color: "var(--sp-text-3)" }}>
                Password
              </label>
              <div className="relative">
                <input
                  id="admin-password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-11 w-full rounded-[10px] pl-3.5 pr-11 text-[15px] outline-none transition-[border-color,box-shadow] duration-200 placeholder:opacity-50 focus:shadow-[0_0_0_3px_var(--sp-lime-18)]"
                  style={inputStyle}
                  onFocus={(e) => (e.currentTarget.style.borderColor = "var(--sp-lime)")}
                  onBlur={(e) => (e.currentTarget.style.borderColor = "var(--sp-border)")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  className="absolute inset-y-0 right-0 flex w-11 items-center justify-center transition-colors"
                  style={{ color: "var(--sp-text-3)" }}
                >
                  {showPassword ? <EyeOff aria-hidden className="h-4 w-4" /> : <Eye aria-hidden className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <p className="text-[13px] font-semibold" role="alert" style={{ color: "var(--sp-error)" }}>
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="flex h-11 items-center justify-center gap-2 rounded-[12px] text-[15px] font-bold transition-all duration-150 active:scale-[0.98] disabled:opacity-70"
              style={{ background: "var(--sp-lime)", color: "var(--sp-lime-fg)" }}
            >
              {busy ? "Signing in…" : "Sign in"}
              {!busy && <ArrowRight aria-hidden className="h-4 w-4" />}
            </button>
          </form>
        </Rise>

        <Rise i={2}>
          <p className="mt-6 flex items-center justify-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.16em]" style={{ color: "var(--sp-text-3)" }}>
            <Lock aria-hidden className="h-3 w-3" />
            Session expires after 12 hours
          </p>
        </Rise>
      </div>
    </main>
  );
}
