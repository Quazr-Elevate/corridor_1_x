"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  version as reactVersion,
  type CSSProperties,
  type ReactNode,
} from "react";
import { cn } from "@/lib/cn";
import type { MediaEntry } from "@/lib/media";
import { Icon, type IconName } from "@/components/ui/Icon";

/**
 * Photo — one photograph from `lib/media`, as an art-directed <picture>.
 *
 *   • WebP renditions via `srcset` + `sizes`, the full JPEG as fallback.
 *   • `portrait` swaps in a portrait crop on phones held upright
 *     (`(max-width: 767px) and (orientation: portrait)`).
 *   • The tiny blurred JPEG paints first; the photo dissolves in over it on
 *     the one expo curve once decoded. The frame is sized up front (fill, or
 *     the image's aspect ratio), so nothing shifts. Opacity only — no scale.
 *   • `priority` for the first screen (sign-in, hero): eager + fetchpriority
 *     high. Everything else loads lazily.
 *
 *   // Full-bleed, art-directed background (parent must be `relative`)
 *   <Photo media={MEDIA.portNight} portrait={MEDIA.portNightPortrait}
 *          fill priority decorative objectPosition="70% center" />
 *
 *   // Card photo in its own aspect box
 *   <Photo media={MEDIA.rice} aspect={4 / 3} rounded={20}
 *          sizes="(min-width: 1024px) 360px, 90vw" />
 */

/** Art direction breakpoint for `portrait` crops. */
export const PORTRAIT_MEDIA = "(max-width: 767px) and (orientation: portrait)";

// React ≥ 18.3 (Next's app-router build) knows `fetchPriority`; older
// releases only pass the lowercase attribute through.
const [major = 0, minor = 0] = reactVersion.split(".").map((n) => parseInt(n, 10));
const FETCH_PRIORITY_ATTR = major > 18 || (major === 18 && minor >= 3) ? "fetchPriority" : "fetchpriority";

export interface PhotoProps {
  media: MediaEntry;
  /** Portrait crop used on upright phones (art direction). Best with `fill`. */
  portrait?: MediaEntry;
  /** Override the entry's alt text. Ignored when `decorative`. */
  alt?: string;
  /** Atmosphere only: empty alt, hidden from assistive tech. */
  decorative?: boolean;
  /**
   * Fill the nearest positioned ancestor (`absolute inset-0`, object-cover).
   * Otherwise the frame takes the photo's aspect ratio (or `aspect`).
   */
  fill?: boolean;
  /** Frame aspect ratio (width / height) when not `fill`. Defaults to the photo's. */
  aspect?: number;
  /** CSS object-position, e.g. "70% center". */
  objectPosition?: string;
  /** `sizes` for the WebP srcset. Defaults to "100vw". */
  sizes?: string;
  /** First-screen image: eager load + fetchpriority high. */
  priority?: boolean;
  /** Dissolve in once loaded (default true). Off: the photo paints over the blur as it arrives. */
  fade?: boolean;
  /** Corner radius for the frame (px number or any CSS length). */
  rounded?: number | string;
  /** Classes for the frame (wrapper). */
  className?: string;
  /** Classes for the <img> (filters, blend modes, hover zoom…). */
  imgClassName?: string;
  style?: CSSProperties;
  imgStyle?: CSSProperties;
  onLoad?: () => void;
  /** Rendered above the photo inside the frame (overlays, gradients, chips). */
  children?: ReactNode;
}

export function Photo({
  media,
  portrait,
  alt,
  decorative = false,
  fill = false,
  aspect,
  objectPosition,
  sizes = "100vw",
  priority = false,
  fade = true,
  rounded,
  className,
  imgClassName,
  style,
  imgStyle,
  onLoad,
  children,
}: PhotoProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  // loaded: the photo has decoded · settled: its dissolve has finished, so
  // the blurred placeholder underneath can go.
  const [loaded, setLoaded] = useState(false);
  const [settled, setSettled] = useState(false);
  const onLoadRef = useRef(onLoad);
  onLoadRef.current = onLoad;

  const markLoaded = useCallback(() => {
    setLoaded(true);
    onLoadRef.current?.();
  }, []);

  // A new photo starts over from its own placeholder.
  const identity = `${media.src}|${portrait?.src ?? ""}`;
  useEffect(() => {
    setLoaded(false);
    setSettled(false);
    // Server-rendered images can finish before hydration attaches onLoad.
    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth > 0) markLoaded();
  }, [identity, markLoaded]);

  // Once the dissolve is done (700ms), drop the placeholder layer.
  useEffect(() => {
    if (!loaded) return;
    if (!fade) {
      setSettled(true);
      return;
    }
    const t = window.setTimeout(() => setSettled(true), 800);
    return () => window.clearTimeout(t);
  }, [loaded, fade]);

  const visible = loaded || !fade;
  const radius = typeof rounded === "number" ? `${rounded}px` : rounded;
  const fit: CSSProperties = objectPosition ? { objectPosition } : {};
  const priorityProps = priority
    ? { [FETCH_PRIORITY_ATTR]: "high", loading: "eager" as const }
    : { loading: "lazy" as const };

  return (
    <div
      className={cn(fill ? "absolute inset-0" : "relative w-full", "overflow-hidden", className)}
      style={{
        ...(fill ? null : { aspectRatio: String(aspect ?? media.aspect) }),
        ...(radius ? { borderRadius: radius } : null),
        ...style,
      }}
    >
      {/* Placeholder: the blurred thumbnail, art-directed like the photo.
          Scaled a touch so the blur has no soft edge inside the frame. */}
      {settled ? null : (
        <picture>
          {portrait ? <source media={PORTRAIT_MEDIA} srcSet={portrait.blurDataURL} /> : null}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={media.blurDataURL}
            alt=""
            aria-hidden="true"
            draggable={false}
            className="pointer-events-none absolute inset-0 size-full scale-110 object-cover blur-xl"
            style={fit}
          />
        </picture>
      )}

      <picture>
        {portrait ? (
          <>
            <source media={PORTRAIT_MEDIA} type="image/webp" srcSet={portrait.webpSrcSet} sizes={sizes} />
            <source media={PORTRAIT_MEDIA} srcSet={portrait.src} />
          </>
        ) : null}
        <source type="image/webp" srcSet={media.webpSrcSet} sizes={sizes} />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          src={media.src}
          alt={decorative ? "" : (alt ?? media.alt)}
          width={media.width}
          height={media.height}
          decoding="async"
          draggable={false}
          {...priorityProps}
          onLoad={markLoaded}
          className={cn(
            "absolute inset-0 size-full object-cover",
            fade && "transition-opacity duration-700 ease-expo",
            visible ? "opacity-100" : "opacity-0",
            imgClassName,
          )}
          style={{ ...fit, ...imgStyle }}
        />
      </picture>

      {children}
    </div>
  );
}

/**
 * PhotoThumb — the small rounded commodity photo used on cards and rows
 * (44px, 14px corners on the reference "Your move" cards). Pass
 * `media={commodityPhoto(category)}`; without a photo it draws the grain
 * tile instead.
 */
export function PhotoThumb({
  media,
  size = 44,
  radius = 14,
  alt,
  fallbackIcon = "grain",
  className,
}: {
  media: MediaEntry | undefined;
  size?: number;
  radius?: number;
  /** Accessible name. Omit for decorative thumbs (the usual case — the row names the lot). */
  alt?: string;
  fallbackIcon?: IconName;
  className?: string;
}) {
  const frame = cn(
    "relative block shrink-0 overflow-hidden shadow-[0_8px_18px_-10px_rgb(90_70_30/0.5)]",
    className,
  );
  const ring = (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 rounded-[inherit] shadow-[inset_0_0_0_1px_rgb(10_10_10/0.06)]"
    />
  );
  if (!media) {
    return (
      <span
        className={cn(
          frame,
          "grain grid place-items-center text-[#8a7a55]",
          "bg-[radial-gradient(120%_120%_at_20%_10%,#efe6d2,#d9ccb0_60%,#cbbd9e)]",
        )}
        style={{ width: size, height: size, borderRadius: radius }}
        role={alt ? "img" : undefined}
        aria-label={alt || undefined}
        aria-hidden={alt ? undefined : true}
      >
        <Icon name={fallbackIcon} size={Math.round(size * 0.45)} />
        {ring}
      </span>
    );
  }
  return (
    <span className={frame} style={{ width: size, height: size, borderRadius: radius }}>
      <Photo
        media={media}
        fill
        decorative={!alt}
        alt={alt}
        sizes={`${size}px`}
        className="rounded-[inherit]"
      />
      {ring}
    </span>
  );
}
