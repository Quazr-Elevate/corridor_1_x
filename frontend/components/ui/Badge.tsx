import { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "autofill" | "optional";

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        "badge",
        tone === "autofill" && "badge-autofill",
        tone === "optional" && "badge-optional",
      )}
    >
      {children}
    </span>
  );
}
