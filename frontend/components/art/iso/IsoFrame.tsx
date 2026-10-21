import type { ReactNode } from "react";
import { ArtSvg, useArtId } from "../ArtSvg";
import { ISO_TONES, type ArtProps, type IsoTone, type Surface } from "../tone";
import { ShadowGrad } from "./core";

export interface IsoCtx {
  t: IsoTone;
  /** Instance-scoped id for gradients, clips and filters. */
  id: (key: string) => string;
  surface: Surface;
}

/**
 * Shared frame for every isometric object: one 240 × 200 viewBox so the
 * whole family sits at the same scale and line weight, plus the shared
 * contact-shadow gradient (`id("sh")`).
 */
export function IsoFrame({
  title,
  className,
  style,
  surface = "trader",
  viewBox = "0 0 240 200",
  children,
}: ArtProps & { viewBox?: string; children: (ctx: IsoCtx) => ReactNode }) {
  const uid = useArtId("iso");
  const t = ISO_TONES[surface];
  const id = (k: string) => `${uid}-${k}`;
  return (
    <ArtSvg viewBox={viewBox} title={title} titleId={id("title")} className={className} style={style}>
      <defs>
        <ShadowGrad id={id("sh")} color={t.shadow} opacity={t.shadowOpacity} />
        <filter id={id("soft")} x="-30%" y="-60%" width="160%" height="220%">
          <feGaussianBlur stdDeviation="5" />
        </filter>
      </defs>
      {children({ t, id, surface })}
    </ArtSvg>
  );
}
