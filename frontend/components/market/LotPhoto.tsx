"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { CommodityArt } from "@/components/art/CommodityArt";
import { Photo } from "@/components/art/Photo";
import { cn } from "@/lib/cn";
import { commodityPhoto } from "@/lib/media";

/**
 * Photography for a lot, in order of truth:
 *   1. the seller's own photo (an uploaded URL),
 *   2. the macro photograph for its commodity (lib/media),
 *   3. the drawn still-life for commodities without one.
 *
 * `LotCover` fills a sized frame (cards, gallery); `LotThumb` is the small
 * rounded square from the reference cards (72px / 20px corners on listing
 * cards, 56px / 14px in previews).
 */

/** An uploaded photo that dissolves in over its commodity's blurred placeholder. */
function UploadedImage({
  src,
  alt,
  category,
  sizes,
  priority,
  imgClassName,
}: {
  src: string;
  alt: string;
  category: string | null | undefined;
  sizes?: string;
  priority?: boolean;
  imgClassName?: string;
}) {
  const ref = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const blur = commodityPhoto(category)?.blurDataURL;

  useEffect(() => {
    setLoaded(false);
    setFailed(false);
    // Server-rendered images can finish before hydration attaches onLoad.
    const img = ref.current;
    if (img && img.complete && img.naturalWidth > 0) setLoaded(true);
  }, [src]);

  if (failed) return <Fallback category={category} sizes={sizes} />;

  return (
    <>
      {blur ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={blur}
          alt=""
          aria-hidden="true"
          className={cn(
            "pointer-events-none absolute inset-0 size-full scale-110 object-cover blur-xl transition-opacity duration-700 ease-expo",
            loaded && "opacity-0",
          )}
        />
      ) : (
        <span aria-hidden="true" className="absolute inset-0 bg-[#e6dac2]" />
      )}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        ref={ref}
        src={src}
        alt={alt}
        decoding="async"
        draggable={false}
        loading={priority ? "eager" : "lazy"}
        onLoad={() => setLoaded(true)}
        onError={() => setFailed(true)}
        className={cn(
          "absolute inset-0 size-full object-cover transition-opacity duration-700 ease-expo",
          loaded ? "opacity-100" : "opacity-0",
          imgClassName,
        )}
      />
    </>
  );
}

function Fallback({
  category,
  sizes,
  alt,
  priority,
  imgClassName,
}: {
  category: string | null | undefined;
  sizes?: string;
  alt?: string;
  priority?: boolean;
  imgClassName?: string;
}) {
  const media = commodityPhoto(category);
  if (media) {
    return (
      <Photo
        media={media}
        fill
        sizes={sizes}
        priority={priority}
        decorative={!alt}
        alt={alt}
        imgClassName={imgClassName}
      />
    );
  }
  return (
    <CommodityArt
      category={category}
      title={alt || undefined}
      className={cn("absolute inset-0 size-full", imgClassName)}
    />
  );
}

/** Fills the nearest positioned ancestor with the lot's best picture. */
export function LotCover({
  src,
  category,
  alt = "",
  sizes = "(min-width: 1024px) 380px, (min-width: 640px) 50vw, 100vw",
  priority,
  imgClassName,
}: {
  /** Resolved URL of the seller's photo, if any. */
  src?: string | null;
  category: string | null | undefined;
  /** Empty = decorative (the card names the lot). */
  alt?: string;
  sizes?: string;
  priority?: boolean;
  imgClassName?: string;
}) {
  return src ? (
    <UploadedImage
      src={src}
      alt={alt}
      category={category}
      sizes={sizes}
      priority={priority}
      imgClassName={imgClassName}
    />
  ) : (
    <Fallback category={category} sizes={sizes} alt={alt} priority={priority} imgClassName={imgClassName} />
  );
}

/** The reference card thumb: a small rounded square with a warm drop shadow. */
export function LotThumb({
  src,
  category,
  size = 72,
  radius = 20,
  alt = "",
  className,
  style,
  children,
}: {
  src?: string | null;
  category: string | null | undefined;
  size?: number;
  radius?: number;
  alt?: string;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}) {
  return (
    <span
      className={cn(
        "relative block shrink-0 overflow-hidden bg-[#e6dac2] shadow-[0_8px_18px_-10px_rgb(90_70_30/0.5)]",
        className,
      )}
      style={{ width: size, height: size, borderRadius: radius, ...style }}
    >
      <LotCover src={src} category={category} alt={alt} sizes={`${size}px`} />
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-[inherit] shadow-[inset_0_0_0_1px_rgb(10_10_10/0.06)]"
      />
      {children}
    </span>
  );
}
