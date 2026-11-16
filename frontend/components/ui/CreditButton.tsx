"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { SpendAction, Wallet } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/Button";
import type { ButtonSize, ButtonVariant } from "@/components/ui/buttonStyles";
import type { IconName } from "@/components/ui/Icon";

export const WALLET_PATH = "/dashboard/wallet";

export interface CreditCost {
  /** Credits this click takes; 0 when a free use covers it. */
  credits: number;
  free: boolean;
  /** Free uses left after this one, when the action has a free quota. */
  freeLeft: number | null;
  balance: number;
  affordable: boolean;
}

/** What `action` would cost this company right now, from its wallet. */
export function creditCost(wallet: Wallet, action: SpendAction): CreditCost {
  const price = wallet.prices.find((p) => p.action === action)?.credits ?? 0;
  const free = action === "RFQ_POST" && (wallet.freeRfqs?.remaining ?? 0) > 0;
  return {
    credits: free ? 0 : price,
    free,
    freeLeft: free && wallet.freeRfqs ? wallet.freeRfqs.remaining - 1 : null,
    balance: wallet.balance,
    affordable: free || wallet.balance >= price,
  };
}

const plural = (n: number) => `${n} ${n === 1 ? "credit" : "credits"}`;

/** "2 credits · you have 18", or "Free · 9 left after this". */
export function costLine(cost: CreditCost): string {
  if (cost.free) return `Free · ${cost.freeLeft} left after this`;
  return `${plural(cost.credits)} · you have ${cost.balance}`;
}

/**
 * The one button for anything that spends credits (build plan 17.3). It
 * prints the price and the balance before the click: "Unlock · 2 credits ·
 * you have 18". When the balance is short it turns into a link to the
 * wallet instead of a button that fails.
 *
 *   <CreditButton wallet={wallet} action="OFFER_UNLOCK" onClick={unlock}>Unlock offer</CreditButton>
 */
export function CreditButton({
  wallet,
  action,
  onClick,
  children,
  loading,
  disabled,
  variant = "primary",
  size = "lg",
  icon,
  block,
  className,
}: {
  /** null while the wallet loads: the button waits rather than guess a price. */
  wallet: Wallet | null;
  action: SpendAction;
  onClick: () => void;
  children: ReactNode;
  loading?: boolean;
  disabled?: boolean;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: IconName;
  block?: boolean;
  className?: string;
}) {
  if (!wallet) {
    return (
      <Button variant={variant} size={size} block={block} className={className} disabled loading>
        {children}
      </Button>
    );
  }
  const cost = creditCost(wallet, action);
  const line = costLine(cost);
  if (!cost.affordable) {
    return (
      <div className={cn("flex flex-col gap-1.5", block && "w-full", className)}>
        <Button variant="secondary" size={size} block={block} disabled icon="lock">
          <span>{children}</span>
          <span aria-hidden="true" className="opacity-50">·</span>
          <span className="t-code">{plural(cost.credits)}</span>
        </Button>
        <p className="t-sub text-fg-3">
          You have {cost.balance}.{" "}
          <Link href={WALLET_PATH} className="font-medium text-fg underline underline-offset-4">
            Top up your wallet
          </Link>
        </p>
      </div>
    );
  }
  return (
    <Button
      variant={variant}
      size={size}
      block={block}
      icon={icon}
      // The label carries the price, so it may wrap on a phone rather than be cut.
      className={cn("h-auto min-h-11 flex-wrap gap-y-0 whitespace-normal py-2", className)}
      loading={loading}
      disabled={disabled}
      onClick={onClick}
    >
      <span>{children}</span>
      <span aria-hidden="true" className="opacity-50">·</span>
      <span className="t-code font-normal">{line}</span>
    </Button>
  );
}
