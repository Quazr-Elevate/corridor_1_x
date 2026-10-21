import { cn } from "@/lib/cn";

/**
 * Frost — means one thing: the API is masking who this is. Decoy glyphs
 * under a blur, never the real name (the identity only reaches the page
 * through the contact reveal). The reference: "Exporter · HR-21 [frost]
 * · Haryana".
 */
export function FrostName({
  width = 110,
  size = "sm",
  label = "Seller name hidden until a verified buyer reveals the contact",
  className,
}: {
  /** Pill width in px. */
  width?: number;
  size?: "sm" | "md";
  label?: string;
  className?: string;
}) {
  return (
    <span
      role="img"
      aria-label={label}
      className={cn(
        "frost inline-flex shrink-0 items-center align-middle",
        size === "sm" ? "h-6 px-2.5" : "h-9 px-4",
        className,
      )}
      style={{ width }}
    >
      <span
        aria-hidden="true"
        className={cn(
          "frost-glyphs truncate whitespace-nowrap font-medium text-fg",
          size === "sm" ? "t-sub" : "t-headline",
        )}
      >
        Xxxxxxx Agro Exports Pvt
      </span>
    </span>
  );
}

/** "Verified seller [frost] · Place" — one line, as on the reference preview card. */
export function SellerLine({
  place,
  lead = "Verified seller",
  frostWidth = 96,
  className,
}: {
  place?: string | null;
  lead?: string;
  frostWidth?: number;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 items-center gap-2", className)}>
      <span className="t-sub shrink-0 font-medium text-fg">{lead}</span>
      <FrostName width={frostWidth} />
      {place ? <span className="t-sub min-w-0 truncate text-fg-3">· {place}</span> : null}
    </div>
  );
}
