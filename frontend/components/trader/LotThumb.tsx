"use client";

import { PhotoThumb } from "@/components/art/Photo";
import type { IconName } from "@/components/ui/Icon";
import { commodityPhoto, type MediaEntry } from "@/lib/media";

/** Drawn glyph for commodities without photography. */
function fallbackIcon(category: string | null | undefined): IconName {
  switch ((category || "").toLowerCase()) {
    case "sugar":
    case "pulses":
    case "spices":
    case "cotton":
      return "sack";
    default:
      return "grain";
  }
}

/**
 * The small rounded commodity photo on move cards, lot rows and the
 * command palette (44px / 14px corners on the reference). Photography
 * from lib/media; the drawn grain tile when the category has none.
 */
export function LotThumb({
  category,
  media,
  size = 44,
  radius = 14,
  className,
}: {
  category?: string | null;
  /** Use this photograph instead of the category's. */
  media?: MediaEntry;
  size?: number;
  radius?: number;
  className?: string;
}) {
  return (
    <PhotoThumb
      media={media ?? commodityPhoto(category)}
      size={size}
      radius={radius}
      fallbackIcon={fallbackIcon(category)}
      className={className}
    />
  );
}
