import Link from "next/link";
import Image from "next/image";
import { ReactNode } from "react";
import { AmbientBackground } from "@/components/brand/AmbientBackground";

interface Props {
  title: string;
  updated: string;
  children: ReactNode;
}

/**
 * Shared shell for /privacy and /terms so both pages carry the same
 * navigation, footer, and ambient background as the rest of the site.
 * Content is written in plain prose — small utility classes on <h2>/<p>
 * keep spacing consistent without pulling in a Markdown pipeline.
 */
export function PolicyShell({ title, updated, children }: Props) {
  return (
    <main className="relative min-h-dvh safe-x overflow-hidden bg-ink text-paper">
      <AmbientBackground />

      <div className="relative mx-auto max-w-2xl px-5 py-14">
        <header className="flex items-center justify-between enter">
          <Link href="/" className="flex items-center">
            <Image
              src="/brand/logo.png"
              alt="Corridor One X"
              width={1998}
              height={320}
              priority
              className="h-6 w-auto select-none sm:h-7"
            />
          </Link>
          <div className="flex items-center gap-3 text-xs text-paper-muted">
            <Link href="/privacy" className="hover:text-paper">Privacy</Link>
            <Link href="/terms" className="hover:text-paper">Terms</Link>
            <Link href="/login" className="hover:text-paper">Sign in</Link>
          </div>
        </header>

        <div className="mt-10 enter" data-delay="2">
          <p className="chip">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
            Legal · effective {updated}
          </p>
          <h1 className="mt-4 text-display sm:text-display-lg text-paper">
            {title}
          </h1>
        </div>

        <article className="prose mt-8 space-y-6 text-sm leading-relaxed text-paper-soft enter" data-delay="4">
          {children}
        </article>

        <footer className="mt-16 border-t border-line-soft pt-6 text-xs text-paper-muted">
          <p>
            Questions?{" "}
            <a href="mailto:privacy@cor1x.com" className="text-accent underline-offset-4 hover:underline">
              privacy@cor1x.com
            </a>{" "}
            — our named Grievance Officer under India&apos;s DPDP Act.
          </p>
        </footer>
      </div>
    </main>
  );
}
