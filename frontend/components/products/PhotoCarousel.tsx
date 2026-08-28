"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { photoUrl } from "@/lib/publicApi";

/**
 * Simple product photo carousel — main tile + thumbnail strip. No swipe
 * gestures yet; keyboard arrows work. Deliberately small — swap for a
 * library only if we grow to gallery/zoom needs.
 */
export function PhotoCarousel({
  photos,
  alt,
}: {
  photos: string[];
  alt: string;
}) {
  const [i, setI] = useState(0);
  const items = photos.length ? photos : [""];
  const current = photoUrl(items[i]);
  const goto = (n: number) => setI((n + items.length) % items.length);

  return (
    <div className="space-y-3">
      <div
        className="relative aspect-[4/3] w-full overflow-hidden rounded-card bg-ink-elevated"
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") goto(i - 1);
          if (e.key === "ArrowRight") goto(i + 1);
        }}
        tabIndex={0}
      >
        {current ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={current}
            alt={alt}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs uppercase tracking-widest text-paper-muted/60">
            no photo
          </div>
        )}
        {items.length > 1 && (
          <>
            <button
              onClick={() => goto(i - 1)}
              className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-ink/60 p-2 text-paper backdrop-blur-sm hover:bg-ink/80"
              aria-label="Previous photo"
              type="button"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => goto(i + 1)}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-ink/60 p-2 text-paper backdrop-blur-sm hover:bg-ink/80"
              aria-label="Next photo"
              type="button"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      {items.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
          {items.map((raw, k) => {
            const url = photoUrl(raw);
            return (
              <button
                key={k}
                onClick={() => setI(k)}
                type="button"
                className={
                  "relative h-14 w-20 shrink-0 overflow-hidden rounded-lg border transition-all " +
                  (k === i
                    ? "border-accent"
                    : "border-line-soft opacity-70 hover:opacity-100")
                }
                aria-label={`Photo ${k + 1}`}
              >
                {url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={url} alt="" className="h-full w-full object-cover" />
                ) : null}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
