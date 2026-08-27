"use client";

import type { TimelinePoint } from "@/lib/adminApi";

export function OnboardingTimeline({ data }: { data: TimelinePoint[] }) {
  const max = Math.max(1, ...data.map((d) => d.buyer + d.seller));
  const totalBuyer = data.reduce((a, d) => a + d.buyer, 0);
  const totalSeller = data.reduce((a, d) => a + d.seller, 0);

  return (
    <div className="mt-5">
      <div className="flex h-40 items-end gap-[3px]">
        {data.map((d) => {
          const buyerH = (d.buyer / max) * 100;
          const sellerH = (d.seller / max) * 100;
          return (
            <div
              key={d.date}
              className="group relative flex flex-1 flex-col justify-end"
              title={`${d.date}: ${d.buyer} buyer + ${d.seller} seller`}
            >
              {sellerH > 0 ? (
                <div
                  className="rounded-t-sm"
                  style={{ height: `${sellerH}%`, background: "var(--violet)" }}
                />
              ) : null}
              {buyerH > 0 ? (
                <div
                  className={sellerH > 0 ? "" : "rounded-t-sm"}
                  style={{ height: `${buyerH}%`, background: "var(--accent)" }}
                />
              ) : null}
              {buyerH === 0 && sellerH === 0 ? (
                <div className="h-[2px] rounded-t-sm bg-line-soft" />
              ) : null}

              {/* Hover tooltip */}
              <div className="pointer-events-none absolute -top-11 left-1/2 z-10 hidden -translate-x-1/2 whitespace-nowrap rounded-md border border-line-soft bg-ink-soft/95 px-2 py-1 text-[10px] text-paper backdrop-blur group-hover:block">
                <p className="text-paper-muted">{d.date}</p>
                <p>
                  <span style={{ color: "var(--accent)" }}>●</span> {d.buyer}
                  <span className="mx-1.5 text-paper-muted">·</span>
                  <span style={{ color: "var(--violet)" }}>●</span> {d.seller}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Axis: first, middle, last dates */}
      <div className="mt-2 flex justify-between text-[10px] text-paper-muted">
        <span>{data[0]?.date ?? ""}</span>
        <span>{data[Math.floor(data.length / 2)]?.date ?? ""}</span>
        <span>{data[data.length - 1]?.date ?? ""}</span>
      </div>

      <p className="mt-3 text-[11px] text-paper-muted">
        Total in window ·{" "}
        <span style={{ color: "var(--accent)" }}>{totalBuyer} buyer</span>
        <span className="mx-1.5">·</span>
        <span style={{ color: "var(--violet)" }}>{totalSeller} seller</span>
      </p>
    </div>
  );
}
