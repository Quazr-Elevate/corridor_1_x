import Link from "next/link";
import { cn } from "@/lib/cn";

/** The Corridor X — four arcs meeting at the crossing. */
export function XMark({ size = 17, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" aria-hidden="true" className={className}>
      <path
        d="M16.1341 1.35123L10.6643 4.88673C9.6445 5.54589 8.33295 5.5459 7.31314 4.88673L1.84338 1.35123L2.71685 0L8.18656 3.53545C8.67479 3.85102 9.30267 3.85101 9.7909 3.53545L15.2607 0L16.1341 1.35123Z"
        fill="currentColor"
      />
      <path
        d="M1.84358 16.6302L7.31334 13.0947C8.33316 12.4356 9.64471 12.4355 10.6645 13.0947L16.1343 16.6302L15.2608 17.9814L9.7911 14.446C9.30288 14.1304 8.67499 14.1304 8.18676 14.446L2.717 17.9814L1.84358 16.6302Z"
        fill="currentColor"
      />
      <path
        d="M16.6281 16.1351L13.0926 10.6653C12.4335 9.64548 12.4335 8.33393 13.0926 7.31412L16.6281 1.84436L17.9794 2.71783L14.4439 8.18754C14.1284 8.67576 14.1284 9.30365 14.4439 9.79188L17.9794 15.2616L16.6281 16.1351Z"
        fill="currentColor"
      />
      <path
        d="M1.35148 1.84615L4.88698 7.31591C5.54614 8.33572 5.54614 9.64727 4.88698 10.6671L1.35148 16.1368L0.000244179 15.2634L3.53569 9.79367C3.85126 9.30544 3.85126 8.67755 3.53569 8.18932L0.000244727 2.71957L1.35148 1.84615Z"
        fill="currentColor"
      />
    </svg>
  );
}

/**
 * Brand lockup. `badge` puts the mark in a solid ink disc (cream/trader
 * pages); `bare` draws the lime mark alone (night/auth pages).
 */
export function Logo({
  href = "/",
  variant = "badge",
  label = "Corridor One X",
  className,
  hideWordmark,
}: {
  href?: string | null;
  variant?: "badge" | "bare";
  label?: string;
  className?: string;
  hideWordmark?: boolean;
}) {
  const inner = (
    <>
      {variant === "badge" ? (
        <span className="solid grid size-10 shrink-0 place-items-center rounded-full text-lime [[data-surface=tower]_&]:bg-lime [[data-surface=tower]_&]:text-ink">
          <XMark size={17} />
        </span>
      ) : (
        <XMark size={20} className="shrink-0 text-lime" />
      )}
      {hideWordmark ? null : (
        <span className="text-[15px] font-medium tracking-[-0.02em]">{label}</span>
      )}
    </>
  );
  const cls = cn("inline-flex items-center gap-2.5", className);
  if (!href) return <span className={cls}>{inner}</span>;
  return (
    <Link href={href} className={cls} aria-label={label}>
      {inner}
    </Link>
  );
}
