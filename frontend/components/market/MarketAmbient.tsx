import { AmbientPhoto } from "@/components/art/AmbientPhoto";
import type { MediaEntry } from "@/lib/media";

/**
 * The photograph behind a market page — the reference's ambient layer
 * (cream ground, drifting light, the photo multiplied in at 30%, blurred
 * 22px and fading out toward the bottom, film grain).
 *
 * Pinned to the viewport *behind this page's content*: render it as the
 * first child of a `relative isolate` page wrapper, so the -z layer stays
 * inside the page's own stacking context whatever the shell does. It
 * dissolves in just after the route transition settles (that transition
 * briefly transforms the page, which would otherwise size a fixed layer
 * to the page box for a moment).
 *
 * Server-safe wrapper; AmbientPhoto itself is a client component.
 */
export function MarketAmbient({ media, opacity }: { media: MediaEntry; opacity?: number }) {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 animate-fade"
      style={{ animationDelay: "450ms" }}
    >
      <AmbientPhoto media={media} opacity={opacity} position="absolute" />
    </div>
  );
}
