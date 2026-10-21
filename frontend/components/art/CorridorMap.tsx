"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { cn } from "@/lib/cn";
import { useArtId } from "./ArtSvg";
import type { Surface } from "./tone";
import { DEFAULT_LANES, PORTS, type Lane, type PortId } from "./map/geo";
import { CAPTION_XY, LAND_PATH, PORT_XY, lanePath, project, viewBoxFor } from "./map/projection";
import { layoutLabels, type Dir, type LabelInput, type Rect } from "./map/labelLayout";

export interface CorridorMapProps {
  /** Which system surface the map sits on. Sets the surface tokens for its labels. */
  surface?: Surface;
  /** Lanes draw on, dashes travel, live ports pulse. Reduced Motion is respected. Default true. */
  animated?: boolean;
  /** Width / height. The map reframes (0.95–1.9) instead of cropping ports. Default 4 / 3. */
  aspect?: number;
  /** Sea lanes to draw (India port → UAE port). Defaults to one lane per India port. */
  lanes?: readonly Lane[];
  /** Ports that carry a beacon ring. Defaults to every port on a lane. Ignored when not animated. */
  live?: readonly PortId[];
  /** Real counts to show beside a port's name (e.g. live listings). Never invent these. */
  counts?: Partial<Record<PortId, number>>;
  /** Quiet region captions (India, UAE, Arabian Sea). Default true. */
  captions?: boolean;
  /** Accessible name. */
  title?: string;
  className?: string;
}

/** Where each port's label prefers to sit (first choice first). */
const PREFER: Record<PortId, readonly Dir[]> = {
  sharjah: ["n", "nw", "ne", "w"],
  "jebel-ali": ["w", "sw", "nw", "s"],
  khalifa: ["sw", "s", "w", "se"],
  kandla: ["ne", "n", "e", "nw"],
  mundra: ["sw", "s", "w", "se"],
  "nhava-sheva": ["e", "se", "ne", "w"],
  kakinada: ["e", "ne", "se", "n"],
};
/** Placement order: crowded clusters first. */
const ORDER: PortId[] = ["sharjah", "jebel-ali", "khalifa", "kandla", "mundra", "nhava-sheva", "kakinada"];

const NOMINAL_W = 560;
/** Layout effect in the browser (measure before paint), plain effect on the server. */
const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;
const MARKER = 8;
/** Below this width labels go compact and captions give way first. */
const COMPACT_BELOW = 480;

function estimateLabel(name: string, count: number | undefined, compact: boolean) {
  const char = compact ? 5.95 : 6.6; // Fragment Mono at 9 / 10px + 0.06em tracking
  const extra = count == null ? 0 : (compact ? 4 : 6) + String(count).length * char;
  return { w: Math.ceil(name.length * char + (compact ? 12 : 16) + extra), h: compact ? 17 : 21 };
}

export function CorridorMap({
  surface = "trader",
  animated = true,
  aspect = 4 / 3,
  lanes = DEFAULT_LANES,
  live,
  counts,
  captions = true,
  title = "India ⇄ UAE corridor",
  className,
}: CorridorMapProps) {
  const uid = useArtId("corridor");
  const id = (k: string) => `${uid}-${k}`;
  const vb = useMemo(() => viewBoxFor(aspect), [aspect]);

  const ports = useMemo(() => {
    const on = new Set<PortId>();
    lanes.forEach((l) => {
      on.add(l.from);
      on.add(l.to);
    });
    return ORDER.filter((p) => on.has(p));
  }, [lanes]);
  const liveSet = useMemo(() => new Set<PortId>(live ?? ports), [live, ports]);
  const paths = useMemo(() => lanes.map((l) => ({ key: `${l.from}-${l.to}`, d: lanePath(l) })), [lanes]);

  const rootRef = useRef<HTMLDivElement>(null);
  const labelRefs = useRef<Partial<Record<PortId, HTMLSpanElement | null>>>({});
  const [size, setSize] = useState({ w: NOMINAL_W, h: NOMINAL_W * (vb.h / vb.w) });
  const [measured, setMeasured] = useState<Partial<Record<PortId, { w: number; h: number }>>>({});

  const compact = size.w < COMPACT_BELOW;

  useIsoLayoutEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const apply = (width: number, height: number) => {
      if (width > 0 && height > 0) {
        setSize((s) => (Math.abs(s.w - width) < 0.5 && Math.abs(s.h - height) < 0.5 ? s : { w: width, h: height }));
      }
    };
    // measure now (before paint), then follow resizes
    const r = el.getBoundingClientRect();
    apply(r.width, r.height);
    const ro = new ResizeObserver(([entry]) => apply(entry.contentRect.width, entry.contentRect.height));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Measure the real label boxes (fonts, counts, compact type) and lay out again.
  useIsoLayoutEffect(() => {
    let cancelled = false;
    const measure = () => {
      if (cancelled) return;
      const next: Partial<Record<PortId, { w: number; h: number }>> = {};
      for (const p of ports) {
        const node = labelRefs.current[p];
        if (node && node.offsetWidth > 0) next[p] = { w: node.offsetWidth, h: node.offsetHeight };
      }
      setMeasured(next);
    };
    measure();
    document.fonts?.ready.then(measure);
    return () => {
      cancelled = true;
    };
  }, [ports, counts, compact]);

  // viewBox units → px of the rendered map
  const k = size.w / vb.w;
  const toPx = (xy: [number, number]): [number, number] => [(xy[0] - vb.x) * k, (xy[1] - vb.y) * k];

  const placed = useMemo(() => {
    const markers: Rect[] = ports.map((p) => {
      const [x, y] = toPx(PORT_XY[p]);
      return { x: x - 5, y: y - 5, w: 10, h: 10 };
    });
    const inputs: LabelInput[] = ports.map((p) => {
      const [x, y] = toPx(PORT_XY[p]);
      const s = measured[p] ?? estimateLabel(PORTS[p].name, counts?.[p], compact);
      return { id: p, x, y, w: s.w, h: s.h, prefer: PREFER[p] };
    });
    return { labels: layoutLabels(inputs, markers, size), markers };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ports, measured, counts, compact, size, vb]);

  // Captions are the quietest layer: each one shows only where it clears every label and marker.
  const captionBoxes = useMemo(() => {
    if (!captions) return [];
    const pad = (r: Rect, p: number) => ({ x: r.x - p, y: r.y - p, w: r.w + 2 * p, h: r.h + 2 * p });
    const blockers = [...placed.labels.map((l) => pad(l.rect, 3)), ...placed.markers.map((r) => pad(r, 1))];
    const clear = (r: Rect) =>
      r.x > 2 &&
      r.x + r.w < size.w - 2 &&
      r.y > 2 &&
      r.y + r.h < size.h - 2 &&
      !blockers.some((b) => r.x < b.x + b.w && b.x < r.x + r.w && r.y < b.y + b.h && b.y < r.y + r.h);
    const out: Array<{ text: string; kind: "land" | "sea"; x: number; y: number; rect: Rect }> = [];
    for (const c of CAPTION_XY) {
      const w = c.text.length * (compact ? 7.4 : 8.6) + 4;
      const h = 14;
      for (const xy of c.xys) {
        const [x, y] = toPx(xy);
        const rect = { x: x - w / 2, y: y - h / 2, w, h };
        if (clear(rect)) {
          out.push({ text: c.text, kind: c.kind, x, y, rect });
          break;
        }
      }
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [captions, placed, compact, size, vb]);

  const pct = (x: number, total: number) => `${(x / total) * 100}%`;
  const glow = project([65.5, 17.5]);

  return (
    <div
      ref={rootRef}
      data-surface={surface}
      role="img"
      aria-label={`${title}: ${ports.map((p) => PORTS[p].name).join(", ")}`}
      className={cn("relative w-full select-none", className)}
      style={{ aspectRatio: `${vb.w} / ${vb.h}` }}
    >
      <svg
        viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
        className="absolute inset-0 h-full w-full"
        aria-hidden
        focusable="false"
      >
        <defs>
          <pattern id={id("dots")} width={6} height={6} patternUnits="userSpaceOnUse">
            <circle cx={3} cy={3} r={1.35} style={{ fill: "var(--c-fg)" }} />
          </pattern>
          {/* edges fade out on all four sides (x fade masked by y fade) */}
          <linearGradient id={id("fx")} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="#000" />
            <stop offset="0.09" stopColor="#fff" />
            <stop offset="0.91" stopColor="#fff" />
            <stop offset="1" stopColor="#000" />
          </linearGradient>
          <linearGradient id={id("fy")} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#000" />
            <stop offset="0.1" stopColor="#fff" />
            <stop offset="0.88" stopColor="#fff" />
            <stop offset="1" stopColor="#000" />
          </linearGradient>
          <mask id={id("my")} maskUnits="userSpaceOnUse" x={vb.x} y={vb.y} width={vb.w} height={vb.h}>
            <rect x={vb.x} y={vb.y} width={vb.w} height={vb.h} fill={`url(#${id("fy")})`} />
          </mask>
          <mask id={id("vignette")} maskUnits="userSpaceOnUse" x={vb.x} y={vb.y} width={vb.w} height={vb.h}>
            <rect
              x={vb.x}
              y={vb.y}
              width={vb.w}
              height={vb.h}
              fill={`url(#${id("fx")})`}
              mask={`url(#${id("my")})`}
            />
          </mask>
          <radialGradient id={id("glow")}>
            <stop offset="0" style={{ stopColor: "var(--c-accent)" }} stopOpacity={surface === "tower" ? 0.11 : 0.09} />
            <stop offset="1" style={{ stopColor: "var(--c-accent)" }} stopOpacity={0} />
          </radialGradient>
        </defs>

        <ellipse cx={glow[0]} cy={glow[1]} rx={vb.w * 0.42} ry={vb.h * 0.42} fill={`url(#${id("glow")})`} />
        <g mask={`url(#${id("vignette")})`}>
          <path d={LAND_PATH} fill={`url(#${id("dots")})`} opacity={surface === "tower" ? 0.36 : 0.3} />
        </g>

        {/* lanes: a quiet full route, the drawn route, then travelling dashes */}
        <g fill="none" strokeLinecap="round" strokeLinejoin="round">
          <g opacity={surface === "tower" ? 0.16 : 0.12} style={{ stroke: "var(--c-fg)" }}>
            {paths.map((p) => (
              <path key={p.key} d={p.d} strokeWidth={1} vectorEffect="non-scaling-stroke" />
            ))}
          </g>
          <g opacity={surface === "tower" ? 0.62 : 0.55} style={{ stroke: "var(--c-fg)" }}>
            {paths.map((p, i) => (
              <path
                key={p.key}
                d={p.d}
                strokeWidth={1.25}
                vectorEffect="non-scaling-stroke"
                pathLength={1}
                className={animated ? "animate-draw" : undefined}
                style={
                  animated
                    ? ({ "--draw-duration": "2.4s", "--draw-delay": `${0.2 + i * 0.3}s` } as CSSProperties)
                    : undefined
                }
              />
            ))}
          </g>
          {animated ? (
            <g
              className="animate-fade"
              style={{ stroke: "var(--c-accent)", animationDelay: `${1.6 + paths.length * 0.3}s`, animationDuration: "1.2s" }}
            >
              {paths.map((p) => (
                <path
                  key={p.key}
                  d={p.d}
                  strokeWidth={1.75}
                  vectorEffect="non-scaling-stroke"
                  className="animate-travel"
                  style={{ "--travel-dash": "2 10" } as CSSProperties}
                />
              ))}
            </g>
          ) : null}
        </g>
      </svg>

      {/* leaders */}
      <svg
        viewBox={`0 0 ${size.w} ${size.h}`}
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden
        focusable="false"
      >
        {placed.labels.map((p) =>
          p.leader ? (
            <line
              key={p.id}
              x1={p.leader[0]}
              y1={p.leader[1]}
              x2={p.leader[2]}
              y2={p.leader[3]}
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
              style={{ stroke: "var(--c-fg)" }}
              opacity={0.35}
            />
          ) : null,
        )}
      </svg>

      {captionBoxes.map((c) => (
        <span
          key={c.text}
          aria-hidden
          className={cn(
            "t-label pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap tracking-[0.22em] text-fg-3",
            compact ? "text-[9px]" : "text-[10px]",
            c.kind === "sea" && "opacity-70",
          )}
          style={{ left: pct(c.x, size.w), top: pct(c.y, size.h) }}
        >
          {c.text}
        </span>
      ))}

      {ports.map((p, i) => {
        const [x, y] = toPx(PORT_XY[p]);
        return (
          <span key={p} aria-hidden className="absolute" style={{ left: pct(x, size.w), top: pct(y, size.h) }}>
            {animated && liveSet.has(p) ? (
              <span
                className="animate-beacon absolute rounded-full bg-lime"
                style={{ left: -MARKER / 2, top: -MARKER / 2, width: MARKER, height: MARKER, animationDelay: `${i * 0.35}s` }}
              />
            ) : null}
            <span
              className="absolute rounded-full bg-lime shadow-[0_0_0_1.5px_#0A0A0A]"
              style={{ left: -MARKER / 2 + 1, top: -MARKER / 2 + 1, width: MARKER - 2, height: MARKER - 2 }}
            />
          </span>
        );
      })}

      {placed.labels.map((pl, i) => {
        const p = pl.id as PortId;
        const count = counts?.[p];
        return (
          <span
            key={p}
            ref={(n) => {
              labelRefs.current[p] = n;
            }}
            aria-hidden
            className={cn(
              "glass t-label absolute flex items-center whitespace-nowrap rounded-full text-fg",
              compact ? "gap-1 px-1.5 py-0.5 text-[9px]" : "gap-1.5 px-2 py-1 text-[10px]",
              animated && "animate-fade",
            )}
            style={{
              left: pct(pl.rect.x, size.w),
              top: pct(pl.rect.y, size.h),
              animationDelay: animated ? `${0.5 + i * 0.08}s` : undefined,
            }}
          >
            {PORTS[p].name}
            {count != null ? <span className="tabular text-accent">{count}</span> : null}
          </span>
        );
      })}
    </div>
  );
}
