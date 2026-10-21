"use client";

import { Chip } from "@/components/ui/Chip";
import { useMe } from "@/lib/useMe";
import { MANDATORY_KEYS } from "@/lib/verification";

/**
 * Marker beside a field label: this is one of the seven fields the
 * Verified badge needs, and whether the *saved* value satisfies it.
 * Driven by `me.verification.missing`, so it flips after a save — not
 * on every keystroke.
 */
export function VerificationBadge({ fieldKey }: { fieldKey: string }) {
  const { me } = useMe();
  if (!MANDATORY_KEYS.has(fieldKey) || !me) return null;
  const filled = !me.verification.missing.includes(fieldKey);
  return filled ? (
    <Chip tone="quiet" icon="check" className="h-5 px-2 text-[11px]">
      For verification
    </Chip>
  ) : (
    <Chip tone="move" noIcon className="h-5 px-2 text-[11px]">
      Needed to verify
    </Chip>
  );
}
