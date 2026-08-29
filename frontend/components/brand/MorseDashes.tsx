/**
 * Decorative dash row — the "morse code" breathing rhythm from the mobile
 * design canvas. Pure CSS, tiny footprint, works as a visual anchor beneath
 * the wordmark or between sections. Not interactive.
 */
export function MorseDashes({
  count = 7,
  className = "",
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div
      className={`flex items-center justify-center gap-1.5 ${className}`}
      aria-hidden
    >
      {Array.from({ length: count }).map((_, i) => (
        <span
          key={i}
          className="h-[1.5px] w-3 rounded-full bg-accent/60"
          style={{
            // Fade the ends so the row reads as breath, not a fence.
            opacity:
              0.35 + 0.65 * Math.sin((Math.PI * (i + 1)) / (count + 1)),
          }}
        />
      ))}
    </div>
  );
}
