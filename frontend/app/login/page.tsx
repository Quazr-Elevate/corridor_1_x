"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import {
  NightCard,
  NightCardFoot,
  NightDivider,
  NightEyebrow,
  NightShell,
  nightLinkClass,
} from "@/components/shell/NightShell";
import { Button, LinkButton } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Notice, Skeleton } from "@/components/ui/Surface";
import { PasswordInput } from "@/components/auth/PasswordInput";

/** Only same-origin paths are valid `next` targets. */
function safeNext(raw: string | null): string {
  if (raw && raw.startsWith("/") && !raw.startsWith("//")) return raw;
  return "/dashboard";
}

function loginError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "That email and password don’t match.";
    if (err.status === 429) return "Too many attempts. Wait a minute, then try again.";
    // 423 — locked after repeated failures; the server says for how long
    // (or that support has to unlock it).
    return err.message;
  }
  return "We couldn’t reach the corridor. Check your connection and try again.";
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const verified = params.get("verified") === "1";
  const wasReset = params.get("reset") === "1";
  const prefill = params.get("email") ?? "";

  const [email, setEmail] = useState(prefill);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await api.login({ email: email.trim().toLowerCase(), password });
      router.replace(next);
      // Keep the button busy until the route changes.
    } catch (err) {
      setError(loginError(err));
      setSubmitting(false);
    }
  }

  return (
    <>
      {verified || wasReset ? (
        <div className="mt-6">
          <Notice tone="verified">
            {wasReset ? "Password reset. Sign in with your new password." : "Email verified. Sign in to continue."}
          </Notice>
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="mt-8 space-y-5">
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
          autoFocus={!prefill}
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <PasswordInput
          night
          size="lg"
          label="Password"
          name="password"
          autoComplete="current-password"
          required
          autoFocus={!!prefill}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error ? (
          <Notice tone="frozen">{error}</Notice>
        ) : null}

        <Button type="submit" variant="night" size="lg" block loading={submitting} iconRight="arrow-right">
          Sign in
        </Button>
        <p className="t-sub text-center text-fg-3">
          <Link href="/forgot-password" className={nightLinkClass}>
            Forgot your password?
          </Link>
          <span className="mt-1 block">Signing in here signs you out on any other device.</span>
        </p>
      </form>

      <NightDivider />
      <LinkButton href="/products" variant="night-quiet" size="lg" block icon="grid">
        Browse the market
      </LinkButton>
    </>
  );
}

function FormFallback() {
  return (
    <div className="mt-8 space-y-5" aria-hidden="true">
      <Skeleton className="h-[78px] rounded-field opacity-40" />
      <Skeleton className="h-[78px] rounded-field opacity-40" />
      <Skeleton className="h-[52px] rounded-field opacity-40" />
    </div>
  );
}

export default function LoginPage() {
  return (
    <NightShell>
      <NightCard as="main">
        <NightEyebrow highlight="India ⇄ UAE">Welcome back</NightEyebrow>
        <h1 className="t-large mt-3 text-cream">
          Sign in to
          <br />
          the corridor.
        </h1>
        <p className="t-callout mt-3 text-fg-2">
          Verified before contact. Masked until escrow. Released on delivery.
        </p>

        <Suspense fallback={<FormFallback />}>
          <LoginForm />
        </Suspense>

        <NightCardFoot>
          New to Corridor?{" "}
          <Link href="/signup" className={nightLinkClass}>
            Get your company verified
          </Link>
        </NightCardFoot>
      </NightCard>
    </NightShell>
  );
}
