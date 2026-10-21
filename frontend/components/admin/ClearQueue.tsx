"use client";

import type { ReactNode } from "react";
import { MEDIA } from "@/lib/media";
import { Photo } from "@/components/art/Photo";
import { Icon, type IconName } from "@/components/ui/Icon";

/**
 * The empty lane — "Queue is clear" — with the inspector photographed in,
 * quietly: the photo sits on the right of a relief card (on top, on
 * phones), dimmed and fading into the card so the copy always reads on
 * clean ink. Decorative photo; the words carry the meaning.
 */
export function ClearQueue({
  eyebrow,
  title,
  children,
  actions,
  icon = "check",
  objectPosition = "62% 40%",
}: {
  eyebrow: ReactNode;
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  icon?: IconName;
  objectPosition?: string;
}) {
  return (
    <section
      aria-label={typeof title === "string" ? title : undefined}
      className="relief relative isolate overflow-hidden rounded-[32px] lg:min-h-[420px]"
    >
      {/* Photo — right half on wide screens, a band on top on phones. */}
      <div className="relative h-52 sm:h-64 lg:absolute lg:inset-y-0 lg:left-auto lg:right-0 lg:h-auto lg:w-[58%]">
        <Photo
          media={MEDIA.inspector}
          fill
          decorative
          objectPosition={objectPosition}
          sizes="(min-width: 1024px) 50vw, 100vw"
          imgClassName="opacity-[0.55] saturate-[0.85]"
        />
        {/* Scrim reaches a few px past the photo so its edge never shows. */}
        <div className="absolute -bottom-1 -left-1 -right-1 top-0 bg-gradient-to-t from-surface via-[rgb(19_19_19/0.55)] to-[rgb(19_19_19/0.15)] lg:-bottom-1 lg:-left-2 lg:-top-1 lg:bg-gradient-to-r lg:from-surface lg:from-[4%] lg:via-[rgb(19_19_19/0.6)] lg:to-[rgb(19_19_19/0.1)]" />
      </div>

      <div className="relative flex flex-col justify-center px-6 pb-8 pt-2 sm:px-9 sm:pb-10 lg:min-h-[420px] lg:max-w-[52%] lg:py-12">
        <span className="grid size-12 place-items-center rounded-full bg-lime text-ink shadow-[0_12px_30px_-14px_rgb(196_216_46/0.7)]">
          <Icon name={icon} size={20} strokeWidth={1.8} />
        </span>
        <p className="t-label mt-6 text-fg-3">{eyebrow}</p>
        <h2 className="t-title1 mt-2 text-fg">{title}</h2>
        {children ? <div className="t-callout mt-3 max-w-md text-fg-2">{children}</div> : null}
        {actions ? <div className="mt-7 flex flex-wrap items-center gap-3">{actions}</div> : null}
      </div>
    </section>
  );
}
