"use client";

import { useEffect, useRef, useState } from "react";
import { MEDIA } from "@/lib/media";
import { PORTRAIT_MEDIA } from "@/components/art/Photo";

/**
 * TowerBackdrop — the ink ground behind the Control Tower, as on the
 * approved reference (portal /ops): a fixed layer with the night port
 * photographed in, screen-blended at 22% so only its lamps and reflections
 * read through the ink, a lime glow low in the frame, a warm one drifting
 * high on the right, and film grain over everything.
 *
 * The photo fades out toward the bottom so long lanes stay calm, and a
 * left-hand scrim keeps the greeting / page titles on clean ink (≥ 4.5:1
 * for the quiet text tokens). Portrait crop on upright phones.
 * Decorative and pointer-transparent; Reduced Motion stops the drift.
 */
const MASK = "linear-gradient(to bottom, #000 0%, #000 42%, transparent 92%)";

export function TowerBackdrop() {
  const imgRef = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth > 0) setLoaded(true);
  }, []);

  const night = MEDIA.portNight;
  const portrait = MEDIA.portNightPortrait;

  return (
    <div aria-hidden="true" className="grain pointer-events-none fixed inset-0 -z-10 overflow-hidden" style={{ position: "fixed" }}>
      <div className="absolute inset-0 bg-ground" />

      <picture>
        <source media={PORTRAIT_MEDIA} type="image/webp" srcSet={portrait.webpSrcSet} sizes="100vw" />
        <source media={PORTRAIT_MEDIA} srcSet={portrait.src} />
        <source type="image/webp" srcSet={night.webpSrcSet} sizes="100vw" />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          src={night.src}
          alt=""
          decoding="async"
          draggable={false}
          onLoad={() => setLoaded(true)}
          className="absolute inset-0 h-full w-full object-cover object-[70%_center] mix-blend-screen transition-opacity duration-1000 ease-expo"
          style={{ opacity: loaded ? 0.22 : 0, maskImage: MASK, WebkitMaskImage: MASK }}
        />
      </picture>

      {/* Scrims: ink on the left (titles), ink at the very top (status line). */}
      <div className="absolute inset-y-0 left-0 w-[70%] bg-gradient-to-r from-[rgb(10_10_10/0.82)] via-[rgb(10_10_10/0.4)] to-transparent" />
      <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-[rgb(10_10_10/0.7)] to-transparent" />

      {/* Light: lime low and centred (reference), warm high on the right. */}
      <div
        className="animate-drift absolute -bottom-[40%] left-[5vw] h-[80vh] w-[90vw] rounded-full blur-3xl"
        style={{ background: "radial-gradient(closest-side, rgb(196 216 46 / 0.1), rgb(196 216 46 / 0))" }}
      />
      <div
        className="animate-drift-reverse absolute -right-[10%] -top-[25%] h-[70vh] w-[55vw] rounded-full blur-3xl"
        style={{ background: "radial-gradient(closest-side, rgb(255 196 130 / 0.07), rgb(255 196 130 / 0))" }}
      />
    </div>
  );
}
