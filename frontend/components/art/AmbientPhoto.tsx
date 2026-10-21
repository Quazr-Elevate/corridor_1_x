"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { cn } from "@/lib/cn";
import { webpAtLeast, type MediaEntry } from "@/lib/media";

/**
 * AmbientPhoto — the photograph *behind* a cream surface, as on the
 * approved reference (portal /corridor): the ground, three warm out-of-focus
 * light blobs (two drifting), and the photo multiplied into the cream —
 * 30% opacity, blur 22px, saturate 1.15, scale 1.08 — fading out toward
 * the bottom, with film grain over everything.
 *
 *   // Behind a whole trader page (the reference: fixed, under content)
 *   <AmbientPhoto media={MEDIA.portDay} position="fixed" className="-z-10" />
 *
 *   // Behind one section (parent must be `relative`)
 *   <AmbientPhoto media={MEDIA.warehouse} opacity={0.24} />
 *
 * Decorative, pointer-transparent. The photo is blurred 22px, so it loads
 * the smallest WebP (640w) and dissolves in on the expo curve. Reduced
 * Motion stops the drift (globals.css); Reduced Transparency is untouched —
 * nothing here is glass.
 */

/** The reference's fade: solid to 30%, gone by 80%. */
const MASK = "linear-gradient(to bottom, #000 0%, #000 30%, transparent 80%)";

export function AmbientPhoto({
  media,
  opacity = 0.3,
  position = "absolute",
  blobs = true,
  grain = true,
  ground = true,
  mask = MASK,
  objectPosition,
  className,
  style,
}: {
  /** The photograph; omit for light and grain only. */
  media?: MediaEntry;
  /** Photo opacity after it loads (reference: 0.3). */
  opacity?: number;
  /** "fixed" pins it to the viewport (page backgrounds); "absolute" fills the parent. */
  position?: "absolute" | "fixed";
  /** Warm radial light blobs (two drift slowly). */
  blobs?: boolean;
  /** Film grain over the layer. */
  grain?: boolean;
  /** Paint the cream ground under everything (turn off over another backdrop). */
  ground?: boolean;
  /** CSS mask for the photo; `false` for none. */
  mask?: string | false;
  objectPosition?: string;
  className?: string;
  style?: CSSProperties;
}) {
  const imgRef = useRef<HTMLImageElement>(null);
  // loaded: the photo has decoded · settled: the crossfade is over and the
  // placeholder can go.
  const [loaded, setLoaded] = useState(false);
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    setLoaded(false);
    setSettled(false);
    // Server-rendered images can finish before hydration attaches onLoad.
    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth > 0) setLoaded(true);
  }, [media?.src]);

  useEffect(() => {
    if (!loaded) return;
    const t = window.setTimeout(() => setSettled(true), 1100);
    return () => window.clearTimeout(t);
  }, [loaded]);

  const photoStyle: CSSProperties = {
    filter: "blur(22px) saturate(1.15)",
    transform: "scale(1.08)",
    ...(mask ? { maskImage: mask, WebkitMaskImage: mask } : null),
    ...(objectPosition ? { objectPosition } : null),
  };

  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none inset-0 overflow-hidden",
        position === "fixed" ? "fixed" : "absolute",
        grain && "grain",
        className,
      )}
      // `.grain` sets position: relative; keep the chosen one.
      style={{ position, ...style }}
    >
      {ground ? <div className="absolute inset-0 bg-ground" /> : null}

      {blobs ? (
        <>
          <div
            className="animate-drift absolute -left-[20%] -top-[30%] h-[90vh] w-[80vw] rounded-full opacity-90 blur-3xl"
            style={{ background: "radial-gradient(closest-side, rgb(255 255 255 / 0.95), rgb(255 255 255 / 0))" }}
          />
          <div
            className="animate-drift-reverse absolute -bottom-[35%] -right-[15%] h-[85vh] w-[70vw] rounded-full blur-3xl"
            style={{ background: "radial-gradient(closest-side, rgb(196 216 46 / 0.16), rgb(196 216 46 / 0))" }}
          />
          <div
            className="absolute bottom-[10%] left-[10%] h-[50vh] w-[40vw] rounded-full blur-3xl"
            style={{ background: "radial-gradient(closest-side, rgb(214 190 150 / 0.22), rgb(214 190 150 / 0))" }}
          />
        </>
      ) : null}

      {media ? (
        <>
          {/* The blurred thumbnail holds the place — at 22px blur it is
              nearly the photo already — and crossfades out as it decodes. */}
          {settled ? null : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={media.blurDataURL}
              alt=""
              className="absolute inset-0 h-full w-full object-cover mix-blend-multiply transition-opacity duration-1000 ease-expo"
              style={{ ...photoStyle, opacity: loaded ? 0 : opacity }}
            />
          )}
          <picture>
            <source type="image/webp" srcSet={webpAtLeast(media, 640)} />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={imgRef}
              src={media.src}
              alt=""
              decoding="async"
              onLoad={() => setLoaded(true)}
              className="absolute inset-0 h-full w-full object-cover mix-blend-multiply transition-opacity duration-1000 ease-expo"
              style={{ ...photoStyle, opacity: loaded ? opacity : 0 }}
            />
          </picture>
        </>
      ) : null}
    </div>
  );
}
