import Link from "next/link";
import type { ReactNode } from "react";
import { AmbientPhoto } from "@/components/art/AmbientPhoto";
import { Photo } from "@/components/art/Photo";
import { Reveal } from "@/components/motion/Reveal";
import { LinkButton } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Logo } from "@/components/ui/Logo";
import { Card, PageHeader } from "@/components/ui/Surface";
import { MEDIA, type MediaKey } from "@/lib/media";

interface Props {
  title: string;
  updated: string;
  /** One line under the title. */
  subtitle?: string;
  /** Photograph behind the page (ambient) and on the side card. */
  media?: MediaKey;
  children: ReactNode;
}

const POLICIES = [
  { href: "/privacy", label: "Privacy Policy", short: "Privacy" },
  { href: "/terms", label: "Terms of Service", short: "Terms" },
] as const;

/**
 * Shared shell for /privacy and /terms — the cream trader ground with the
 * reference's ambient photograph behind everything (multiplied in, blurred,
 * fading down the page), no signed-in chrome (no /me fetch). The logo
 * badge and a small glass nav float on top; the policy reads in a relief
 * card, with a photographed side card for contact and the other policy.
 */
export function PolicyShell({ title, updated, subtitle, media = "portDay", children }: Props) {
  const photo = MEDIA[media];
  const isPrivacy = title.startsWith("Privacy");
  const other = POLICIES.find((p) => (isPrivacy ? p.href === "/terms" : p.href === "/privacy"))!;

  return (
    <div data-surface="trader" className="relative isolate min-h-dvh text-fg">
      <AmbientPhoto media={photo} position="fixed" className="-z-10" />

      <header className="sticky top-[env(safe-area-inset-top,0px)] z-40 px-4 pt-4 sm:px-8 sm:pt-5">
        <div className="mx-auto flex max-w-page items-center justify-between gap-3">
          <div className="glass rounded-full p-1.5 pr-4 sm:pr-5">
            <Logo href="/" />
          </div>
          <nav aria-label="Legal" className="glass flex items-center gap-1 rounded-full p-1.5">
            {POLICIES.map((p) => (
              <NavLink key={p.href} href={p.href} current={p.href === (isPrivacy ? "/privacy" : "/terms")}>
                {p.short}
              </NavLink>
            ))}
            <LinkButton href="/login" size="sm" className="hidden rounded-full sm:inline-flex">
              Sign in
            </LinkButton>
          </nav>
        </div>
      </header>

      <main className="relative mx-auto w-full max-w-page px-4 pb-20 pt-8 sm:px-8 sm:pt-12">
        <PageHeader eyebrow="Legal · India ⇄ UAE" title={title} subtitle={subtitle} />

        {/* phones and tablets: the photograph leads (the side card carries it on desktop) */}
        <div className="relief mt-8 rounded-card p-2 animate-rise lg:hidden">
          <Photo media={photo} aspect={21 / 9} rounded={22} decorative sizes="92vw" priority />
        </div>

        <div className="mt-8 grid items-start gap-6 sm:mt-10 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-8">
          <Card as="article" className="px-5 py-7 sm:px-10 sm:py-10">
            <p className="t-label text-fg-3">Last updated · {updated}</p>
            <div
              className={
                "t-body mt-6 max-w-[68ch] space-y-6 text-fg-2 " +
                "[&_b]:font-semibold [&_b]:text-fg " +
                "[&_code]:rounded-[6px] [&_code]:bg-fg/5 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[12.5px] [&_code]:text-fg " +
                "[&_ul]:space-y-2.5"
              }
            >
              {children}
            </div>
          </Card>

          <Reveal as="aside" aria-label="About this policy" className="space-y-4 lg:sticky lg:top-28">
            <div className="relief overflow-hidden rounded-card p-2.5">
              <Photo
                media={photo}
                aspect={4 / 3}
                rounded={20}
                decorative
                sizes="280px"
                className="hidden lg:block"
              />
              <div className="px-3 pb-3 pt-4 max-lg:pt-3">
                <p className="t-label text-fg-3">Contact</p>
                <p className="t-callout mt-2 text-fg-2">
                  Questions?{" "}
                  <a
                    href="mailto:privacy@cor1x.com"
                    className="rounded-sm text-accent underline-offset-4 hover:underline"
                  >
                    privacy@cor1x.com
                  </a>{" "}
                  — our named Grievance Officer under India&apos;s DPDP Act.
                </p>
              </div>
            </div>

            <Link
              href={other.href}
              className="relief-sm relief-hover group flex items-center justify-between gap-3 rounded-[22px] px-5 py-4"
            >
              <span>
                <span className="t-label block text-fg-3">Also read</span>
                <span className="t-headline mt-1 block text-fg">{other.label}</span>
              </span>
              <span className="grid size-9 shrink-0 place-items-center rounded-full text-fg-2 transition-colors group-hover:text-fg">
                <Icon name="arrow-right" size={17} />
              </span>
            </Link>
          </Reveal>
        </div>
      </main>
    </div>
  );
}

function NavLink({ href, current, children }: { href: string; current: boolean; children: ReactNode }) {
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={
        "inline-flex h-9 items-center rounded-full px-3.5 text-[13px] font-medium transition-colors duration-300 " +
        (current ? "bg-fg/[0.06] text-fg" : "text-fg-2 hover:bg-fg/5 hover:text-fg")
      }
    >
      {children}
    </Link>
  );
}
