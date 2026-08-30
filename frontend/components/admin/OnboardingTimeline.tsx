"use client";

import type { TimelinePoint } from "@/lib/adminApi";

// Two-series, brand-aligned: buyer = lime, seller = muted olive (themed). No third hue.
const BUYER = "var(--sp-lime)";
const SELLER = "var(--sp-seller)";

export function OnboardingTimeline({ data }: { data: TimelinePoint[] }) {
  const max = Math.max(1, ...data.map((d) => d.buyer + d.seller));
  const totalBuyer = data.reduce((a, d) => a + d.buyer, 0);
  const totalSeller = data.reduce((a, d) => a + d.seller, 0);

  return (
    <div className="mt-5">
      <div className="flex h-40 items-end gap-[3px]">
        {data.map((d, idx) => {
          const buyerH = (d.buyer / max) * 100;
          const sellerH = (d.seller / max) * 100;
          const empty = buyerH === 0 && sellerH === 0;
          return (
            <div
              key={d.date}
              className="group relative flex flex-1 flex-col justify-end"
              title={`${d.date}: ${d.buyer} buyer + ${d.seller} seller`}
            >
              <div
                className="flex flex-col justify-end"
                style={{
                  // Bars grow up on entry, staggered across the window.
                  transformOrigin: "bottom",
                  animation: `spBarGrow 0.5s var(--sp-ease) ${0.15 + idx * 0.012}s both`,
                }}
              >
                {sellerH > 0 && (
                  <div className="rounded-t-[3px]" style={{ height: `${sellerH * 1.6}px`, background: SELLER }} />
                )}
                {buyerH > 0 && (
                  <div className={sellerH > 0 ? "" : "rounded-t-[3px]"} style={{ height: `${buyerH * 1.6}px`, background: BUYER }} />
                )}
                {empty && <div className="h-[2px] rounded-t-[3px]" style={{ background: "var(--sp-border)" }} />}
              </div>

              <div
                className="pointer-events-none absolute -top-12 left-1/2 z-10 hidden -translate-x-1/2 whitespace-nowrap rounded-[8px] px-2.5 py-1.5 text-[10px] backdrop-blur group-hover:block"
                style={{ border: "1px solid var(--sp-border)", background: "var(--sp-tooltip)", color: "var(--sp-text)" }}
              >
                <p style={{ color: "var(--sp-text-3)" }}>{d.date}</p>
                <p className="mt-0.5">
                  <span style={{ color: BUYER }}>●</span> {d.buyer}
                  <span className="mx-1.5" style={{ color: "var(--sp-text-3)" }}>·</span>
                  <span style={{ color: SELLER }}>●</span> {d.seller}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-2 flex justify-between text-[10px]" style={{ color: "var(--sp-text-3)" }}>
        <span>{data[0]?.date ?? ""}</span>
        <span>{data[Math.floor(data.length / 2)]?.date ?? ""}</span>
        <span>{data[data.length - 1]?.date ?? ""}</span>
      </div>

      <p className="mt-3 text-[11px]" style={{ color: "var(--sp-text-3)" }}>
        Total in window ·{" "}
        <span style={{ color: BUYER }}>{totalBuyer} buyer</span>
        <span className="mx-1.5">·</span>
        <span style={{ color: SELLER }}>{totalSeller} seller</span>
      </p>
    </div>
  );
}
