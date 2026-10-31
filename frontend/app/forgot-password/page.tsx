"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { NightCard, NightCardFoot, NightEyebrow, NightShell, nightLinkClass } from "@/components/shell/NightShell";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Notice } from "@/components/ui/Surface";
import { PasswordInput } from "@/components/auth/PasswordInput";

const MIN_PASSWORD = 8;

/**
 * Forgot password — email → 6-digit code → new password. The first step
 * answers the same way whether or not the account exists. Resetting signs
 * the account out everywhere; a support lock stays until support unlocks it.
 */
export default function ForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState<"email" | "reset">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function sendCode(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const r = await api.forgotPassword(email.trim().toLowerCase());
      setInfo(r.devCode ? `${r.message} (dev code: ${r.devCode})` : r.message);
      setStep("reset");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn’t reach the corridor. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function reset(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    if (password.length < MIN_PASSWORD) return setError(`Use at least ${MIN_PASSWORD} characters.`);
    if (password !== confirm) return setError("Passwords don’t match.");
    setBusy(true);
    try {
      await api.resetPassword({ email: email.trim().toLowerCase(), code, newPassword: password });
      router.replace("/login?reset=1");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn’t reach the corridor. Try again.");
      setBusy(false);
    }
  }

  return (
    <NightShell>
      <NightCard as="main">
        <NightEyebrow highlight="Account">Reset password</NightEyebrow>
        <h1 className="t-large mt-3 text-cream">
          {step === "email" ? "Forgot your password?" : "Choose a new password."}
        </h1>
        <p className="t-callout mt-3 text-fg-2">
          {step === "email"
            ? "Enter your work email and we’ll send a 6-digit code."
            : "Enter the code from your inbox. Resetting signs you out on every device."}
        </p>

        {step === "email" ? (
          <form onSubmit={sendCode} className="mt-8 space-y-5">
            <Input
              night
              size="lg"
              label="Work email"
              type="email"
              name="email"
              autoComplete="username"
              inputMode="email"
              autoCapitalize="none"
              spellCheck={false}
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {error ? <Notice tone="frozen">{error}</Notice> : null}
            <Button type="submit" variant="night" size="lg" block loading={busy} iconRight="arrow-right">
              Send code
            </Button>
          </form>
        ) : (
          <form onSubmit={reset} className="mt-8 space-y-5">
            {info ? <Notice tone="verified">{info}</Notice> : null}
            <Input
              night
              size="lg"
              label="6-digit code"
              name="code"
              autoComplete="one-time-code"
              inputMode="numeric"
              maxLength={12}
              required
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
            <PasswordInput
              night
              size="lg"
              label="New password"
              name="new-password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <PasswordInput
              night
              size="lg"
              label="Confirm new password"
              name="confirm-password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            {error ? <Notice tone="frozen">{error}</Notice> : null}
            <Button type="submit" variant="night" size="lg" block loading={busy} iconRight="arrow-right">
              Reset password
            </Button>
            <button
              type="button"
              className={`t-sub block w-full text-center ${nightLinkClass}`}
              onClick={() => {
                setStep("email");
                setError(null);
                setCode("");
              }}
            >
              Use a different email or resend the code
            </button>
          </form>
        )}

        <NightCardFoot>
          Remembered it?{" "}
          <Link href="/login" className={nightLinkClass}>
            Back to sign in
          </Link>
        </NightCardFoot>
      </NightCard>
    </NightShell>
  );
}
