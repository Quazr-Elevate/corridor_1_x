import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon, type IconName } from "./Icon";

/** Relief card — content you can touch. 28px radius. */
export function Card({
  className,
  interactive,
  as: Tag = "div",
  children,
  ...rest
}: HTMLAttributes<HTMLElement> & {
  interactive?: boolean;
  as?: "div" | "section" | "article" | "li";
}) {
  return (
    <Tag
      className={cn(
        "relief rounded-card",
        interactive && "relief-hover cursor-pointer",
        className,
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
}

/** Solid ink panel — certainty (verified identity, executed state). */
export function SolidPanel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div data-surface="tower" className={cn("solid-panel relative overflow-hidden rounded-card text-fg", className)}>
      {children}
    </div>
  );
}

/** Page header: mono eyebrow, large title, body subtitle, optional actions. */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  size = "large",
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  size?: "hero" | "large" | "title1";
  className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-end justify-between gap-x-8 gap-y-5", className)}>
      <div className="min-w-0 max-w-2xl animate-rise">
        {eyebrow ? <p className="t-label text-fg-3">{eyebrow}</p> : null}
        <h1
          className={cn(
            "mt-3 text-fg",
            size === "hero" && "t-hero",
            size === "large" && "t-large",
            size === "title1" && "t-title1",
          )}
        >
          {title}
        </h1>
        {subtitle ? <p className="t-body mt-3 text-fg-2">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
    </header>
  );
}

/** Section heading inside a page. */
export function SectionTitle({
  title,
  meta,
  dot,
  className,
}: {
  title: ReactNode;
  meta?: ReactNode;
  dot?: "move" | "verified" | "frozen";
  className?: string;
}) {
  return (
    <div className={cn("flex items-center justify-between gap-4", className)}>
      <h2 className="t-title3 flex items-center gap-2.5 text-fg">
        {dot ? (
          <span
            className={cn(
              "size-2 rounded-full",
              dot === "move" && "bg-amber",
              dot === "verified" && "bg-lime",
              dot === "frozen" && "bg-danger",
            )}
          />
        ) : null}
        {title}
      </h2>
      {meta ? <div className="t-sub text-fg-3">{meta}</div> : null}
    </div>
  );
}

/**
 * Inline notice band.
 *   info     sunk well, neutral
 *   move     amber — your move
 *   frozen   danger — rejected / blocked (announced as an alert)
 *   verified lime-soft / olive — certain
 *   night    quiet frost for night glass (auth screens)
 * `className` styles the band; `actionClassName` the action slot.
 */
export type NoticeTone = "info" | "move" | "frozen" | "verified" | "night";

export function Notice({
  tone = "info",
  title,
  children,
  action,
  icon: iconProp,
  className,
  actionClassName,
}: {
  tone?: NoticeTone;
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  /** Override the tone's glyph. */
  icon?: IconName;
  className?: string;
  actionClassName?: string;
}) {
  const icon: IconName =
    iconProp ??
    (tone === "frozen" ? "alert" : tone === "verified" ? "shield" : tone === "move" ? "clock" : "info");
  const neutral = tone === "info" || tone === "night";
  return (
    <div
      role={tone === "frozen" ? "alert" : "status"}
      className={cn(
        "flex flex-col gap-3 rounded-[20px] p-4 sm:flex-row sm:items-center sm:gap-4",
        tone === "info" && "well",
        tone === "move" && "bg-amber-soft text-amber",
        tone === "frozen" && "bg-danger-soft text-danger",
        tone === "verified" && "bg-lime-soft text-accent",
        tone === "night" && "bg-white/[0.06] text-cream shadow-[inset_0_0_0_1px_rgb(255_255_255/0.09)]",
        className,
      )}
    >
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <Icon
          name={icon}
          size={18}
          className={cn("mt-0.5 shrink-0", tone === "info" && "text-fg-2", tone === "night" && "text-cream/70")}
        />
        <div className="min-w-0">
          {title ? (
            <p className={cn("t-headline", tone === "info" && "text-fg", tone === "night" && "text-cream")}>{title}</p>
          ) : null}
          {children ? (
            <div
              className={cn(
                "t-callout",
                title && "mt-0.5",
                tone === "info" && "text-fg-2",
                tone === "night" && "text-cream/75",
                !neutral && "opacity-90",
              )}
            >
              {children}
            </div>
          ) : null}
        </div>
      </div>
      {action ? <div className={cn("shrink-0", actionClassName)}>{action}</div> : null}
    </div>
  );
}

/** Empty state — a drawn glyph in a relief disc, a line, an action. */
export function EmptyState({
  icon = "grain",
  title,
  children,
  action,
  className,
}: {
  icon?: IconName;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-14 text-center", className)}>
      <span className="relief-sm grid size-14 place-items-center rounded-full text-fg-2">
        <Icon name={icon} size={22} />
      </span>
      <p className="t-title3 mt-5 text-fg">{title}</p>
      {children ? <p className="t-callout mt-2 max-w-sm text-fg-2">{children}</p> : null}
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

/** Loading placeholder — a sunk well that shimmers. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("well relative overflow-hidden rounded-[14px]", className)} aria-hidden="true">
      <div className="absolute inset-y-0 left-0 w-1/3 animate-shimmer bg-gradient-to-r from-transparent via-white/40 to-transparent [[data-surface=tower]_&]:via-white/5" />
    </div>
  );
}

/** Key/value stat with mono label (e.g. "IN THE CORRIDOR 5"). */
export function Stat({
  label,
  value,
  sub,
  className,
  align = "left",
}: {
  label: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  className?: string;
  align?: "left" | "right";
}) {
  return (
    <div className={cn(align === "right" && "text-right", className)}>
      <p className="t-label text-fg-3">{label}</p>
      <div className="t-title1 tabular mt-2 text-fg">{value}</div>
      {sub ? <p className="t-foot mt-1 text-fg-3">{sub}</p> : null}
    </div>
  );
}

/** Drawn commodity tile — grain until photography lands. */
export function CommodityTile({
  src,
  alt = "",
  className,
  icon = "grain",
}: {
  src?: string | null;
  alt?: string;
  className?: string;
  icon?: IconName;
}) {
  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={src} alt={alt} className={cn("rounded-[14px] object-cover", className)} />
    );
  }
  return (
    <div
      className={cn(
        "grain grid place-items-center overflow-hidden rounded-[14px] text-[#8a7a55]",
        "bg-[radial-gradient(120%_120%_at_20%_10%,#efe6d2,#d9ccb0_60%,#cbbd9e)]",
        className,
      )}
      aria-hidden={alt ? undefined : true}
      role={alt ? "img" : undefined}
      aria-label={alt || undefined}
    >
      <Icon name={icon} size={22} />
    </div>
  );
}
