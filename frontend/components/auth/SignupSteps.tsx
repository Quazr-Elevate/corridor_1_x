import { cn } from "@/lib/cn";
import { Icon } from "@/components/ui/Icon";

/**
 * Sign-up stepper — the onboarding reference's chips, on night glass:
 * the current step is solid with a lime number disc, steps behind you
 * carry a check, steps ahead sit quiet in a well.
 *
 * Steps are the real in-page flow: work email → 6-digit code → name and
 * password.
 */
const STEPS = ["Email", "Code", "Account"] as const;

export function SignupSteps({ current, className }: { current: number; className?: string }) {
  return (
    <ol
      aria-label="Sign-up steps"
      className={cn("no-scrollbar -mx-1 flex items-center gap-1.5 overflow-x-auto px-1 py-0.5", className)}
    >
      {STEPS.map((label, i) => {
        const done = i < current;
        const here = i === current;
        return (
          <li key={label} aria-current={here ? "step" : undefined} className="shrink-0">
            <span
              className={cn(
                "t-sub flex h-8 items-center gap-1.5 whitespace-nowrap rounded-full pl-1.5 pr-3 font-medium transition-colors duration-500 ease-expo",
                here && "solid",
                done && "text-fg-2 shadow-[inset_0_0_0_1px_rgb(255_255_255/0.1)]",
                !here && !done && "text-fg-3",
              )}
            >
              <span
                className={cn(
                  "t-code grid size-5 place-items-center rounded-full text-[10px]",
                  here && "bg-lime text-ink",
                  done && "bg-lime-soft text-accent",
                  !here && !done && "well",
                )}
              >
                {done ? <Icon name="check" size={12} strokeWidth={2} /> : i + 1}
              </span>
              {label}
              {done ? <span className="sr-only"> (done)</span> : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
