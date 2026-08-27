"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Eye, EyeOff, Lock, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { adminApi } from "@/lib/adminApi";

export default function AdminLoginPage() {
  const router = useRouter();
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

  return (
    <main className="flex min-h-screen items-center justify-center bg-ink px-4 text-paper">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-line-soft bg-ink-elevated">
            <ShieldCheck className="h-5 w-5 text-accent" aria-hidden />
          </span>
          <p className="mt-4 text-[10px] uppercase tracking-widest text-paper-muted">
            Cor1x · Admin console
          </p>
          <h1 className="mt-2 text-display text-paper">Operator sign in</h1>
          <p className="mt-2 text-sm text-paper-muted">
            Restricted to authorized operators.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="surface space-y-5 p-5 sm:p-6" noValidate>
          <TextField
            id="f-admin-email"
            label="Email"
            type="email"
            placeholder="admin@cor1x.local"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          {/* Password with eye toggle — inline instead of TextField because the
              trailing icon needs to be clickable. */}
          <div>
            <label htmlFor="f-admin-password" className="field-label">
              <span>Password</span>
            </label>
            <div className="relative">
              <input
                id="f-admin-password"
                type={showPassword ? "text" : "password"}
                className="field pr-10"
                placeholder="••••••••"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-paper-muted transition-colors hover:text-paper"
              >
                {showPassword ? (
                  <EyeOff aria-hidden className="h-4 w-4" />
                ) : (
                  <Eye aria-hidden className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          {error ? (
            <p className="text-sm font-medium text-danger" role="alert">
              {error}
            </p>
          ) : null}
          <Button type="submit" loading={busy} className="w-full">
            <span>Sign in</span>
            <ArrowRight aria-hidden className="h-4 w-4" />
          </Button>
        </form>

        <p className="mt-6 flex items-center justify-center gap-1.5 text-[10px] uppercase tracking-widest text-paper-muted">
          <Lock aria-hidden className="h-3 w-3" />
          Session expires after 12 hours
        </p>
      </div>
    </main>
  );
}
