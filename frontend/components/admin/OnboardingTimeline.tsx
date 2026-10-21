"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import type { UserDetail } from "@/lib/adminApi";
import { Icon } from "@/components/ui/Icon";
import { fmtDateTime } from "./format";

type StepState = "done" | "current" | "todo" | "blocked";

interface Step {
  key: string;
  label: string;
  meta?: ReactNode;
  state: StepState;
}

function buildSteps(u: UserDetail): Step[] {
  const raw: Array<Omit<Step, "state"> & { done: boolean; blocked?: boolean }> = [
    { key: "signup", label: "Signed up", meta: fmtDateTime(u.createdAt), done: true },
    {
      key: "email",
      label: "Email confirmed",
      meta: u.emailVerifiedAt ? fmtDateTime(u.emailVerifiedAt) : "Not yet",
      done: !!u.emailVerifiedAt,
    },
    {
      key: "submitted",
      label: "Sent for verification",
      meta: u.verificationSubmittedAt ? fmtDateTime(u.verificationSubmittedAt) : "Not yet",
      done: !!u.verificationSubmittedAt || u.status === "verified",
    },
    u.status === "rejected"
      ? {
          key: "decision",
          label: "Rejected",
          meta: u.verificationRejectedReason ?? "No reason recorded",
          done: false,
          blocked: true,
        }
      : {
          key: "decision",
          label: "Verified",
          meta: u.verifiedAt ? fmtDateTime(u.verifiedAt) : u.status === "pending_verification" ? "In review" : "Not yet",
          done: u.status === "verified",
        },
  ];

  let currentSet = false;
  return raw.map(({ done, blocked, ...s }) => {
    if (blocked) return { ...s, state: "blocked" as const };
    if (done) return { ...s, state: "done" as const };
    if (!currentSet) {
      currentSet = true;
      return { ...s, state: "current" as const };
    }
    return { ...s, state: "todo" as const };
  });
}

/** Vertical corridor rail for one account: behind = solid, here = lime, ahead = well. */
export function OnboardingTimeline({ user, className }: { user: UserDetail; className?: string }) {
  const steps = buildSteps(user);
  return (
    <ol className={cn("relative", className)} aria-label="Onboarding timeline">
      {steps.map((s, i) => {
        const last = i === steps.length - 1;
        return (
          <li key={s.key} className="relative flex gap-4 pb-5 last:pb-0">
            {!last ? (
              <span
                aria-hidden="true"
                className={cn(
                  "absolute left-[13px] top-8 h-[calc(100%-2.25rem)] w-[3px] rounded-full",
                  s.state === "done" ? "bg-[#edefea]" : "well",
                )}
              />
            ) : null}
            <span
              className={cn(
                "t-code relative z-10 grid size-7 shrink-0 place-items-center rounded-full text-[11px]",
                s.state === "done" && "solid",
                s.state === "current" && "bg-lime text-ink shadow-[0_0_0_5px_rgb(196_216_46/0.22)]",
                s.state === "todo" && "well text-fg-3",
                s.state === "blocked" && "bg-danger-soft text-danger",
              )}
              aria-current={s.state === "current" ? "step" : undefined}
            >
              {s.state === "done" ? (
                <Icon name="check" size={13} strokeWidth={2} />
              ) : s.state === "blocked" ? (
                <Icon name="alert" size={13} />
              ) : (
                i + 1
              )}
            </span>
            <div className="min-w-0 pt-0.5">
              <p
                className={cn(
                  "t-callout font-medium",
                  s.state === "todo" ? "text-fg-3" : s.state === "blocked" ? "text-danger" : "text-fg",
                )}
              >
                {s.label}
                <span className="sr-only">
                  {" "}
                  — {s.state === "done" ? "done" : s.state === "current" ? "current step" : s.state === "blocked" ? "blocked" : "to do"}
                </span>
              </p>
              {s.meta ? <p className="t-sub mt-0.5 break-words text-fg-3">{s.meta}</p> : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
