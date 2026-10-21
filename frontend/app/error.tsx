"use client";

import { useEffect } from "react";
import { NightCard, NightCardFoot, NightEyebrow, NightShell } from "@/components/shell/NightShell";
import { Button, LinkButton } from "@/components/ui/Button";

/**
 * Route error boundary — same night language as the 404. Offers a retry
 * (re-renders the segment) and a way home; shows the digest so support
 * can find the server log line.
 */
export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface it in the console for whoever is debugging; the UI stays calm.
    console.error(error);
  }, [error]);

  return (
    <NightShell>
      <NightCard as="main">
        <NightEyebrow highlight="Error">Something went wrong</NightEyebrow>
        <h1 className="t-large mt-3 text-cream">
          We lost the signal
          <br />
          for a moment.
        </h1>
        <p className="t-callout mt-3 text-fg-2">
          This page hit a problem loading. Try again — if it keeps happening, start over from the
          front door.
        </p>

        <div className="mt-8 flex flex-col gap-3">
          <Button variant="night" size="lg" block icon="refresh" onClick={() => reset()}>
            Try again
          </Button>
          <LinkButton href="/" variant="night-quiet" size="lg" block icon="arrow-left">
            Back to the front door
          </LinkButton>
        </div>

        {error.digest ? (
          <NightCardFoot>
            <p className="t-label">
              Reference · <span className="t-code select-all normal-case text-fg-2">{error.digest}</span>
            </p>
          </NightCardFoot>
        ) : null}
      </NightCard>
    </NightShell>
  );
}
