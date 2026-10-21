import type { Metadata } from "next";
import Link from "next/link";
import { NightCard, NightCardFoot, NightEyebrow, NightShell, nightLinkClass } from "@/components/shell/NightShell";
import { LinkButton } from "@/components/ui/Button";

export const metadata: Metadata = {
  title: "Page not found — Corridor One X",
};

/** 404 — the night port, one short line and the two ways back. */
export default function NotFound() {
  return (
    <NightShell>
      <NightCard as="main">
        <NightEyebrow highlight="404">Off the corridor</NightEyebrow>
        <h1 className="t-large mt-3 text-cream">
          This page isn’t
          <br />
          on the corridor.
        </h1>
        <p className="t-callout mt-3 text-fg-2">
          The link may be old, or the page has moved. The market and your account are where you left
          them.
        </p>

        <div className="mt-8 flex flex-col gap-3">
          <LinkButton href="/" variant="night" size="lg" block icon="arrow-left">
            Back to the front door
          </LinkButton>
          <LinkButton href="/products" variant="night-quiet" size="lg" block icon="grid">
            Browse the market
          </LinkButton>
        </div>

        <NightCardFoot>
          Signed in?{" "}
          <Link href="/dashboard" className={nightLinkClass}>
            Go to your corridor
          </Link>
        </NightCardFoot>
      </NightCard>
    </NightShell>
  );
}
