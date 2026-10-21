import { cn } from "@/lib/cn";
import { ArtSvg, useArtId } from "./ArtSvg";
import { H, W } from "./commodity/layout";
import { Scene, type ArtCategory } from "./commodity/scenes";
import { StillLife } from "./commodity/StillLife";
import type { CSSProperties } from "react";

export type { ArtCategory };

/** Categories that are drawn (the rest have macro photographs in `lib/media`). */
export const ART_CATEGORIES: readonly ArtCategory[] = ["Oilseeds", "Cotton", "Millets", "Tea", "Coffee", "Other"];

const BY_LOWER = new Map(ART_CATEGORIES.map((c) => [c.toLowerCase(), c]));

/** Normalise any listing category to a drawn one ("Other" for anything unknown). */
export function artCategory(category: string | null | undefined): ArtCategory {
  return BY_LOWER.get((category ?? "").trim().toLowerCase()) ?? "Other";
}

const TITLES: Record<ArtCategory, string> = {
  Oilseeds: "Groundnuts, mustard and sesame seed on hessian",
  Cotton: "Open cotton bolls on hessian",
  Millets: "Pearl millet grain and a millet head on hessian",
  Tea: "Black tea leaf and a fresh tea sprig on hessian",
  Coffee: "Roasted coffee beans on hessian",
  Other: "A wooden sampling scoop of mixed grain on hessian",
};

/**
 * CommodityArt — a drawn macro still-life for categories without a
 * photograph (Oilseeds, Cotton, Millets, Tea, Coffee, Other). Warm sand
 * hessian, window light from the top-left, soft background — the mood of
 * the macro photographs, so a drawn tile sits beside a photo tile.
 *
 * Fills its box like `object-fit: cover` (the subject stays inside the
 * 4:3, 1:1 and 16:10 safe area). Give the box a size:
 *
 *   <div className="relative aspect-[4/3] overflow-hidden rounded-[20px]">
 *     <CommodityArt category={product.category} className="absolute inset-0 h-full" />
 *   </div>
 *
 * Without a sized box it renders at 4:3 (`h-auto w-full`). `variant`
 * re-scatters the items so neighbouring tiles of one category differ.
 * Server-safe (no client JS). Decorative unless `title` is given; pass
 * `title` (or `labelled`) when the picture carries meaning.
 */
export function CommodityArt({
  category,
  variant = 0,
  title,
  labelled,
  className,
  style,
}: {
  category: string | null | undefined;
  variant?: number;
  /** Accessible name; overrides the built-in description. */
  title?: string;
  /** Use the built-in description as the accessible name. */
  labelled?: boolean;
  className?: string;
  style?: CSSProperties;
}) {
  const cat = artCategory(category);
  const uid = useArtId("s");
  const gid = (k: string) => `${uid}-${k}`;
  const seed = Math.abs(Math.round(variant)) % 97;
  return (
    <ArtSvg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid slice"
      title={title ?? (labelled ? TITLES[cat] : undefined)}
      titleId={gid("title")}
      className={cn("bg-[#E6DAC2]", className)}
      style={style}
    >
      <StillLife gid={gid}>
        <Scene category={cat} seed={seed} gid={gid} />
      </StillLife>
    </ArtSvg>
  );
}
