import { cn } from "@/lib/cn";

/**
 * Beacon — the amber "your move" dot with a breathing ring (reference:
 * portal /corridor, "Your move"). The ring is a loop, never a reveal, and
 * stops under Reduced Motion (globals.css).
 */
export function Beacon({ className, still }: { className?: string; still?: boolean }) {
  return (
    <span aria-hidden="true" className={cn("relative inline-grid size-2 shrink-0 place-items-center", className)}>
      {still ? null : <span className="animate-beacon absolute inset-0 rounded-full bg-amber" />}
      <span className="relative size-2 rounded-full bg-amber" />
    </span>
  );
}
