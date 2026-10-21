"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { adminApi } from "@/lib/adminApi";
import { NightCard, NightCardFoot, NightEyebrow, NightShell } from "@/components/shell/NightShell";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Notice } from "@/components/ui/Surface";
import { PasswordInput } from "@/components/auth/PasswordInput";

function adminError(err: unknown): string {
  const status = (err as { status?: number } | null)?.status;
  if (status === 401) return "Those credentials don’t open the tower.";
  if (status === 429) return "Too many attempts. Wait a minute, then try again.";
  if (err instanceof Error && err.message) return err.message;
  return "We couldn’t reach the tower. Check your connection and try again.";
}

export default function AdminLoginPage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Already signed in? Go straight up.
  useEffect(() => {
    let alive = true;
    adminApi
      .me()
      .then(() => {
        if (alive) router.replace("/admin");
      })
      .catch(() => {
        if (alive) setChecking(false);
      });
    return () => {
      alive = false;
    };
  }, [router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      await adminApi.login(email.trim().toLowerCase(), password);
      router.replace("/admin");
    } catch (err) {
      setError(adminError(err));
      setBusy(false);
    }
  }

  return (
    <NightShell
      tag="Control tower"
      tone="tower"
      linksLabel="Ops"
      links={[
        { href: "/login", label: "Trader sign-in", icon: "arrow-left" },
        { href: "/privacy", label: "Privacy", icon: "lock" },
        { href: "/terms", label: "Terms", icon: "file" },
      ]}
    >
      <NightCard as="main">
        <NightEyebrow highlight="Restricted">Operators</NightEyebrow>
        <h1 className="t-large mt-3 text-cream">Open the tower.</h1>
        <p className="t-callout mt-3 text-fg-2">Restricted to Corridor operators.</p>

        <form onSubmit={onSubmit} className="mt-8 space-y-5" aria-busy={checking || undefined}>
          <Input
            night
            size="lg"
            label="Email"
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
          <PasswordInput
            night
            size="lg"
            label="Password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error ? <Notice tone="frozen">{error}</Notice> : null}

          <Button
            type="submit"
            variant="night"
            size="lg"
            block
            loading={busy || checking}
            iconRight="arrow-right"
          >
            Enter the tower
          </Button>
        </form>

        <NightCardFoot>
          <p className="t-label flex items-center gap-2">
            <Icon name="lock" size={13} />
            Sessions expire after 12 hours
          </p>
        </NightCardFoot>
      </NightCard>
    </NightShell>
  );
}
