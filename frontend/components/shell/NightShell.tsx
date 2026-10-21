import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { MEDIA } from "@/lib/media";
import { Photo } from "@/components/art/Photo";
import { Icon, type IconName } from "@/components/ui/Icon";
import { XMark } from "@/components/ui/Logo";

/**
 * Night — the arrival surfaces (landing, sign-in, sign-up, ops sign-in,
 * 404 / error). Built like the approved reference (portal /arrive):
 *
 *   • a full-bleed night-port photograph (portrait crop on upright phones,
 *     framed at 70% so the open water on the left carries the text),
 *   • an ink gradient from the left and from the bottom so cream text
 *     keeps ≥ 4.5:1 on the photo,
 *   • two warm out-of-focus glows (sodium amber + a breath of lime),
 *   • the wordmark top-left, a glass-night card, and a glass-night footer
 *     pill with the © line.
 *
 * `tone="tower"` is the ops variant: cooler and darker, desaturated photo.
 */

export type NightTone = "port" | "tower";

export interface NightLink {
  href: string;
  label: string;
  icon: IconName;
}

const DEFAULT_LINKS: readonly NightLink[] = [
  { href: "/products", label: "Market", icon: "grid" },
  { href: "/privacy", label: "Privacy", icon: "lock" },
  { href: "/terms", label: "Terms", icon: "file" },
];

export function NightShell({
  children,
  footer,
  links = DEFAULT_LINKS,
  linksLabel = "Explore",
  className,
  tag,
  tone = "port",
}: {
  children: ReactNode;
  /** Replaces the footer pill (the © line stays). */
  footer?: ReactNode;
  /** Links in the footer pill. */
  links?: readonly NightLink[];
  /** Mono label at the start of the footer pill. */
  linksLabel?: string;
  /** Classes for the content row (the card's flex container). */
  className?: string;
  /** Small mono tag after the wordmark, e.g. "Control tower". */
  tag?: string;
  tone?: NightTone;
}) {
  return (
    <div data-surface="tower" className="relative min-h-dvh overflow-hidden bg-ink text-fg">
      <NightBackdrop tone={tone} />
      <div className="relative z-10 mx-auto flex min-h-dvh max-w-[1360px] flex-col px-4 py-6 sm:px-10 sm:py-10">
        <header className="flex items-center gap-3 text-cream">
          <NightWordmark />
          {tag ? (
            <span className="t-label rounded-full bg-lime-soft px-2.5 py-1 text-accent">{tag}</span>
          ) : null}
        </header>
        <div className={cn("flex flex-1 items-center py-10", className)}>{children}</div>
        <footer className="flex flex-wrap items-center justify-between gap-4">
          {footer ?? <NightPill label={linksLabel} links={links} />}
          <p className="t-foot text-cream/75 [text-shadow:0_1px_14px_rgb(0_0_0/0.7)]">
            © {new Date().getFullYear()} Corridor One X · Verified trade infrastructure for India &amp; the Gulf
          </p>
        </footer>
      </div>
    </div>
  );
}

/** Lime X + wordmark, as on the reference's night header. */
export function NightWordmark({ className }: { className?: string }) {
  return (
    <Link
      href="/"
      aria-label="Corridor One X — home"
      className={cn("inline-flex items-center gap-3 rounded-full text-cream", className)}
    >
      <XMark size={22} className="shrink-0 text-lime" />
      <span className="text-[16px] font-medium tracking-[-0.02em]">Corridor One X</span>
    </Link>
  );
}

/**
 * The scene behind every night page: photo, overlays, glows. Fills the
 * nearest positioned ancestor. Decorative.
 *
 * `scrim="text"` is for copy set straight on the photo (the landing hero):
 * below 1024px the text runs over the lit cranes, so the ink is heavier
 * there. Behind a glass card the reference's lighter overlays are enough.
 */
export function NightBackdrop({
  tone = "port",
  scrim = "card",
  className,
}: {
  tone?: NightTone;
  scrim?: "card" | "text";
  className?: string;
}) {
  const tower = tone === "tower";
  const text = scrim === "text";
  return (
    <div aria-hidden="true" className={cn("pointer-events-none absolute inset-0", className)}>
      <Photo
        media={MEDIA.portNight}
        portrait={MEDIA.portNightPortrait}
        fill
        priority
        decorative
        objectPosition="70% center"
        sizes="100vw"
        imgClassName={tower ? "saturate-[0.45] brightness-[0.72]" : undefined}
      />
      {/* ink from the left (text side) and from the bottom (footer) */}
      <div
        className={cn(
          "absolute inset-0 bg-gradient-to-r",
          tower ? "from-ink/80 via-ink/50 to-ink/20" : "from-ink/60 via-ink/25 to-transparent",
          text && "max-lg:from-ink/70 max-lg:via-ink/45 max-lg:to-ink/20",
        )}
      />
      <div
        className={cn(
          "absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t to-transparent",
          tower ? "from-ink/75" : "from-ink/60",
        )}
      />
      {text ? (
        <div className="absolute inset-x-0 top-0 h-[55%] bg-gradient-to-b from-ink/45 to-transparent lg:hidden" />
      ) : null}
      {tower ? (
        <div className="absolute inset-0 bg-[#0b1420]/35 mix-blend-multiply" />
      ) : null}

      {/* out-of-focus light */}
      <div
        className="absolute left-[8%] top-[18%] h-[70vh] w-[46vw] rounded-full opacity-90 blur-3xl"
        style={glow(tower ? "150 190 230" : "255 168 84", tower ? 0.08 : 0.16)}
      />
      <div
        className="absolute left-[2%] top-[4%] h-[40vh] w-[28vw] rounded-full blur-3xl"
        style={glow("196 216 46", tower ? 0.1 : 0.08)}
      />
      <div className="grain absolute inset-0 [&::after]:opacity-[0.05] [&::after]:mix-blend-screen" />
    </div>
  );
}

function glow(rgb: string, alpha: number): CSSProperties {
  return { background: `radial-gradient(closest-side, rgb(${rgb} / ${alpha}), rgb(${rgb} / 0))` };
}

/** Glass-night pill of links (the reference's footer shortcuts). */
export function NightPill({
  label,
  links,
  className,
}: {
  label?: string;
  links: readonly NightLink[];
  className?: string;
}) {
  return (
    <nav
      aria-label={label ?? "Links"}
      className={cn(
        "glass-night no-scrollbar flex max-w-full items-center gap-1 overflow-x-auto rounded-full p-1",
        className,
      )}
    >
      {label ? <span className="t-label shrink-0 px-3 text-fg-3">{label}</span> : null}
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className="t-sub flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-full px-3.5 font-medium text-fg-2 transition-colors duration-300 ease-expo hover:bg-white/[0.07] hover:text-fg"
        >
          <Icon name={l.icon} size={16} />
          {l.label}
        </Link>
      ))}
    </nav>
  );
}

/** The floating glass-night card that holds a form (reference: 460px, 34px corners). */
export function NightCard({
  children,
  className,
  style,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  as?: "div" | "section" | "main";
}) {
  return (
    <Tag
      style={style}
      className={cn(
        "glass-night w-full max-w-[460px] animate-rise rounded-[34px] p-7 text-cream sm:p-9",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

/** Card eyebrow: mono label with an optional lime highlight ("… · India ⇄ UAE"). */
export function NightEyebrow({ children, highlight }: { children: ReactNode; highlight?: ReactNode }) {
  return (
    <p className="t-label text-fg-3">
      {children}
      {highlight ? (
        <>
          {" · "}
          <span className="text-accent">{highlight}</span>
        </>
      ) : null}
    </p>
  );
}

/** "or" rule between two ways in. */
export function NightDivider({ children = "or" }: { children?: ReactNode }) {
  return (
    <div className="my-5 flex items-center gap-3">
      <span aria-hidden="true" className="h-px flex-1 bg-line" />
      <span className="t-foot text-fg-3">{children}</span>
      <span aria-hidden="true" className="h-px flex-1 bg-line" />
    </div>
  );
}

/** The card's closing line, above a hairline. */
export function NightCardFoot({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("t-sub mt-8 border-t border-line pt-5 text-fg-3", className)}>{children}</div>;
}

/** Link style used inside the card foot. */
export const nightLinkClass =
  "rounded-sm font-semibold text-fg underline decoration-fg/30 underline-offset-4 transition-colors hover:decoration-fg";
