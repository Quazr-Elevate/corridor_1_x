"use client";

import Link from "next/link";
import { ArrowRight, KeyRound, UserRound, Package } from "lucide-react";
import { useMe } from "@/lib/useMe";
import { RejectedDocsPopup } from "@/components/dashboard/RejectedDocsPopup";
import { RejectedVerificationPopup } from "@/components/dashboard/RejectedVerificationPopup";
import { VerificationProgress } from "@/components/dashboard/VerificationProgress";

export default function DashboardPage() {
  const { me } = useMe();
  const firstName = me?.primary.fullName?.split(" ")[0] || "there";

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <RejectedDocsPopup />
      <RejectedVerificationPopup />
      {me?.mustChangePassword && (
        <Link
          href="/dashboard/settings"
          className="group block rounded-card border border-amber-400/30 bg-amber-400/5 p-4 transition hover:border-amber-400/50"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-field bg-amber-400/15 text-amber-400">
              <KeyRound className="h-4 w-4" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-paper">
                Set a real password
              </p>
              <p className="text-xs text-paper-muted leading-relaxed">
                You&apos;re signed in with the temp password from the welcome
                email. Open Settings → Security &amp; Privacy to pick a real one.
              </p>
            </div>
            <ArrowRight
              className="h-4 w-4 text-paper-muted group-hover:text-amber-400 transition"
              aria-hidden
            />
          </div>
        </Link>
      )}
      <VerificationProgress />
      <header>
        <p className="text-[10px] uppercase tracking-widest text-paper-muted">
          Welcome back
        </p>
        <h1 className="mt-2 text-display text-paper">
          Hey, <span className="text-gradient">{firstName}</span>
        </h1>
        <p className="mt-2 text-sm text-paper-muted">
          Your Cor1x home. Head to My Account to review your details and upload
          certifications.
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2">
        <HomeTile
          href="/dashboard/account"
          icon={UserRound}
          title="My Account"
          body="Primary info, company info, business profile, and certifications."
        />
        <HomeTile
          href="#"
          icon={Package}
          title="Listings"
          body="Create and manage product offerings. Coming soon."
          soon
        />
      </section>
    </div>
  );
}

function HomeTile({
  href,
  icon: Icon,
  title,
  body,
  soon,
}: {
  href: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  title: string;
  body: string;
  soon?: boolean;
}) {
  const content = (
    <div className="group h-full rounded-card border border-line-soft bg-ink-soft/70 p-6 transition hover:border-accent/40">
      <div className="flex items-start justify-between gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-field bg-accent/10 text-accent">
          <Icon className="h-5 w-5" />
        </div>
        {soon ? (
          <span className="rounded-pill border border-line-soft bg-ink px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-paper-muted">
            Soon
          </span>
        ) : (
          <ArrowRight className="h-4 w-4 text-paper-muted group-hover:text-accent transition" />
        )}
      </div>
      <h2 className="mt-5 text-title text-paper">{title}</h2>
      <p className="mt-2 text-sm text-paper-muted leading-relaxed">{body}</p>
    </div>
  );
  if (soon) return <div className="opacity-70 cursor-not-allowed">{content}</div>;
  return <Link href={href}>{content}</Link>;
}
