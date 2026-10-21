"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import type { TimelinePoint } from "@/lib/adminApi";

const H = 184;
const PAD = { top: 12, right: 4, bottom: 26, left: 30 };

function niceMax(max: number) {
  if (max <= 4) return Math.max(1, max);
  const step = Math.pow(10, Math.floor(Math.log10(max)));
  for (const m of [1, 2, 2.5, 5, 10]) {
    if (m * step >= max) return m * step;
  }
  return 10 * step;
}

function dayLabel(iso: string, long = false) {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", long ? { weekday: "short", day: "numeric", month: "short" } : { day: "numeric", month: "short" });
}

/** Bar with a 4px rounded data end, anchored square to the baseline. */
function barPath(x: number, y: number, w: number, h: number) {
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

/**
 * Daily signups — one series, honest zero baseline. Bars in fg-3, today in
 * lime. Hover / arrow keys show the day; a hidden table carries the data.
 */
export function SignupChart({ data, className }: { data: ReadonlyArray<TimelinePoint>; className?: string }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const [hover, setHover] = useState<number | null>(null);
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(el);
    setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const n = data.length;
  const total = useMemo(() => data.reduce((a, d) => a + d.count, 0), [data]);
  const max = useMemo(() => niceMax(Math.max(0, ...data.map((d) => d.count))), [data]);
  const peak = useMemo(
    () => data.reduce<TimelinePoint | null>((p, d) => (!p || d.count > p.count ? d : p), null),
    [data],
  );

  const plotW = Math.max(0, w - PAD.left - PAD.right);
  const plotH = H - PAD.top - PAD.bottom;
  const slot = n ? plotW / n : 0;
  const gap = Math.min(4, Math.max(2, slot * 0.28));
  const barW = Math.max(1, slot - gap);
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH;
  const ticks = max <= 1 ? [0, 1] : [0, max / 2, max];
  const labelIdx = n > 2 ? [0, Math.floor((n - 1) / 2), n - 1] : n ? [0, n - 1] : [];

  const active = hover !== null ? data[hover] : null;
  const tipLeft = hover !== null ? PAD.left + hover * slot + slot / 2 : 0;

  const desc = n
    ? `${total} signups across ${n} days, from ${dayLabel(data[0].date)} to ${dayLabel(data[n - 1].date)}. ` +
      (peak && peak.count > 0 ? `Busiest day ${dayLabel(peak.date)} with ${peak.count}. ` : "") +
      `Today: ${data[n - 1].count}.`
    : "No data.";

  return (
    <div className={cn("relative", className)}>
      <div
        ref={wrap}
        className="relative rounded-[14px] outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--focus)]"
        style={{ height: H }}
        tabIndex={0}
        aria-labelledby={titleId}
        aria-describedby={descId}
        onKeyDown={(e) => {
          if (!n) return;
          if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
            e.preventDefault();
            const d = e.key === "ArrowRight" ? 1 : -1;
            setHover((h) => Math.max(0, Math.min(n - 1, (h ?? n - 1) + (h === null ? 0 : d))));
          } else if (e.key === "Escape") {
            setHover(null);
          }
        }}
        onBlur={() => setHover(null)}
        onPointerLeave={() => setHover(null)}
      >
        {w > 0 ? (
          <svg width={w} height={H} role="img" aria-labelledby={`${titleId} ${descId}`} className="block overflow-visible">
            <title id={titleId}>Daily signups, last {n} days</title>
            <desc id={descId}>{desc}</desc>

            {ticks.map((t) => (
              <g key={t}>
                <line
                  x1={PAD.left}
                  x2={w - PAD.right}
                  y1={y(t)}
                  y2={y(t)}
                  stroke="var(--c-line)"
                  strokeWidth={1}
                  strokeDasharray={t === 0 ? undefined : "2 4"}
                />
                <text
                  x={PAD.left - 8}
                  y={y(t)}
                  dy="0.35em"
                  textAnchor="end"
                  className="t-label fill-current text-fg-3"
                  style={{ fontSize: 10 }}
                >
                  {Number.isInteger(t) ? t : t.toFixed(1)}
                </text>
              </g>
            ))}

            {data.map((d, i) => {
              const x = PAD.left + i * slot + gap / 2;
              const today = i === n - 1;
              const h = (d.count / max) * plotH;
              const fill = today ? "#C4D82E" : hover === i ? "var(--c-fg-2)" : "var(--c-fg-3)";
              return (
                <g key={d.date}>
                  {d.count > 0 ? (
                    <path d={barPath(x, y(d.count), barW, h)} fill={fill} opacity={today || hover === i ? 1 : 0.55} />
                  ) : (
                    <rect x={x} y={y(0) - 2} width={barW} height={2} rx={1} fill={today ? "#C4D82E" : "var(--c-line-2)"} />
                  )}
                  {/* Hit target: the whole column, bigger than the mark. */}
                  <rect
                    x={PAD.left + i * slot}
                    y={PAD.top}
                    width={slot}
                    height={plotH}
                    fill="transparent"
                    onPointerEnter={() => setHover(i)}
                    onPointerDown={() => setHover(i)}
                  />
                </g>
              );
            })}

            {labelIdx.map((i, k) => (
              <text
                key={`${i}-${k}`}
                x={PAD.left + i * slot + slot / 2}
                y={H - 6}
                textAnchor={k === 0 ? "start" : k === labelIdx.length - 1 ? "end" : "middle"}
                dx={k === 0 ? -slot / 2 + gap / 2 : k === labelIdx.length - 1 ? slot / 2 - gap / 2 : 0}
                className="t-label fill-current text-fg-3"
                style={{ fontSize: 10 }}
              >
                {i === n - 1 ? "TODAY" : dayLabel(data[i].date).toUpperCase()}
              </text>
            ))}
          </svg>
        ) : null}

        {active ? (
          <div
            aria-hidden="true"
            className="glass pointer-events-none absolute -top-2 z-10 whitespace-nowrap rounded-[14px] px-3 py-2"
            style={{
              left: Math.min(Math.max(tipLeft, 70), Math.max(70, w - 70)),
              transform: "translate(-50%, -100%)",
            }}
          >
            <p className="t-label text-fg-3">{dayLabel(active.date, true)}</p>
            <p className="t-headline tabular mt-0.5 text-fg">
              {active.count} signup{active.count === 1 ? "" : "s"}
            </p>
          </div>
        ) : null}
      </div>

      <p className="sr-only" aria-live="polite">
        {active ? `${dayLabel(active.date, true)}: ${active.count} signups` : ""}
      </p>

      <table className="sr-only">
        <caption>Daily signups</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Signups</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.date}>
              <th scope="row">{d.date}</th>
              <td>{d.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
