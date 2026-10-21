"use client";

import { useCallback, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import type { IconName } from "@/components/ui/Icon";
import { LotCover, LotThumb } from "@/components/market/LotPhoto";
import { cn } from "@/lib/cn";
import { photoUrl } from "@/lib/publicApi";

/**
 * Lot gallery — a large photograph with the reference's 72px rounded
 * thumbs underneath. Arrow keys move between photos when the gallery has
 * focus; Home/End jump to the ends. Photos dissolve in (opacity only).
 *
 * Without seller photos it shows the commodity's macro photograph (or the
 * drawn still-life), labelled as a category photo so nobody mistakes it
 * for the lot itself.
 */
export function PhotoCarousel({
  photos,
  alt,
  category,
}: {
  photos: string[];
  alt: string;
  /** The lot's category — picks the fallback photograph. */
  category?: string | null;
  /** @deprecated drawn glyphs gave way to photography; kept for old callers. */
  icon?: IconName;
}) {
  const urls = photos.map((p) => photoUrl(p)).filter((u): u is string => !!u);
  const [i, setI] = useState(0);
  const count = urls.length;
  const goto = useCallback((n: number) => setI(count ? (n + count) % count : 0), [count]);

  const frame =
    "relative aspect-[4/3] w-full overflow-hidden rounded-[30px] bg-[#e6dac2] shadow-[0_40px_70px_-40px_rgb(70_55_25/0.55),inset_0_0_0_1px_rgb(10_10_10/0.06)]";

  if (!count) {
    return (
      <figure className={frame}>
        <LotCover category={category} alt={`${alt} — category photo`} priority sizes="(min-width: 1024px) 680px, 100vw" />
        <figcaption className="glass t-sub absolute bottom-4 left-4 inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-fg-2">
          <Icon name="image" size={15} />
          Category photo — the seller hasn&rsquo;t added one yet
        </figcaption>
      </figure>
    );
  }

  return (
    <div role="region" aria-roledescription="carousel" aria-label={`${alt} photos`}>
      <div
        tabIndex={count > 1 ? 0 : -1}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") {
            e.preventDefault();
            goto(i - 1);
          } else if (e.key === "ArrowRight") {
            e.preventDefault();
            goto(i + 1);
          } else if (e.key === "Home") {
            e.preventDefault();
            goto(0);
          } else if (e.key === "End") {
            e.preventDefault();
            goto(count - 1);
          }
        }}
        className={cn(frame, "focus-visible:rounded-[30px]")}
      >
        <LotCover
          key={urls[i]}
          src={urls[i]}
          category={category}
          alt={count > 1 ? `${alt} — photo ${i + 1} of ${count}` : alt}
          priority={i === 0}
          sizes="(min-width: 1024px) 680px, 100vw"
        />
        {count > 1 ? (
          <>
            <NavButton side="left" label="Previous photo" onClick={() => goto(i - 1)} />
            <NavButton side="right" label="Next photo" onClick={() => goto(i + 1)} />
            <span
              aria-live="polite"
              className="glass t-code absolute bottom-4 right-4 rounded-full px-2.5 py-1 text-fg"
            >
              {i + 1}/{count}
            </span>
          </>
        ) : null}
      </div>

      {count > 1 ? (
        <ul className="no-scrollbar mt-4 flex gap-3 overflow-x-auto p-1" aria-label="Choose a photo">
          {urls.map((u, k) => (
            <li key={u + k} className="shrink-0">
              <button
                type="button"
                onClick={() => setI(k)}
                aria-label={`Photo ${k + 1}`}
                aria-current={k === i ? "true" : undefined}
                className={cn(
                  "block rounded-[18px] transition-[box-shadow,opacity] duration-300 ease-expo focus-visible:rounded-[18px]",
                  k === i
                    ? "shadow-[0_0_0_2px_var(--c-ground),0_0_0_4px_var(--c-fg)]"
                    : "opacity-70 hover:opacity-100",
                )}
              >
                <LotThumb src={u} category={category} size={72} radius={18} />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function NavButton({ side, label, onClick }: { side: "left" | "right"; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        "glass absolute top-1/2 grid size-11 -translate-y-1/2 place-items-center rounded-full text-fg transition-opacity duration-300",
        side === "left" ? "left-4" : "right-4",
      )}
    >
      <Icon name={side === "left" ? "arrow-left" : "arrow-right"} size={18} />
    </button>
  );
}
