import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Reveal } from "@/components/motion/Reveal";

/** Section heading on the ink landing: mono eyebrow, large title, one body line. */
export function SectionHead({
  id,
  eyebrow,
  title,
  body,
  aside,
  className,
}: {
  id?: string;
  eyebrow: string;
  title: ReactNode;
  body?: ReactNode;
  /** Right-hand slot (a link, a chip). */
  aside?: ReactNode;
  className?: string;
}) {
  return (
    <Reveal as="header" className={cn("flex flex-wrap items-end justify-between gap-x-10 gap-y-5", className)}>
      <div className="min-w-0 max-w-[720px]">
        <p className="t-label flex items-center gap-2 text-fg-3">
          <span aria-hidden="true" className="size-1.5 rounded-full bg-lime" />
          {eyebrow}
        </p>
        <h2 id={id} className="t-large mt-4 text-cream">
          {title}
        </h2>
        {body ? <p className="t-body mt-4 max-w-[58ch] text-fg-2 sm:text-[16px]">{body}</p> : null}
      </div>
      {aside ? <div className="shrink-0">{aside}</div> : null}
    </Reveal>
  );
}

/** The page measure every landing section shares with the hero. */
export const landingWrap = "mx-auto w-full max-w-[1360px] px-4 sm:px-10";
