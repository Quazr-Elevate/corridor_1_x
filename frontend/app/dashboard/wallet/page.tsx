"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type CreditPlan, type LedgerLine, type Purchase, type SpendAction, type Wallet } from "@/lib/api";
import { formatDay } from "@/lib/verification";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { CreditButton } from "@/components/ui/CreditButton";
import { Card, EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";

const ACTION_LABEL: Record<SpendAction, string> = {
  RFQ_POST: "Post a request for quotation",
  OFFER_UNLOCK: "Unlock an offer",
  RFQ_VIEW: "View a request for quotation",
  LISTING_BOOST: "Boost a listing",
  AI_QUERY: "Ask the assistant",
  SAMPLE_FEE: "Request a sample",
};

const LINE_LABEL: Record<LedgerLine["entryType"], string> = {
  ...ACTION_LABEL,
  PLAN_PURCHASE: "Plan purchase",
  TOP_UP: "Top-up",
  ADJUSTMENT: "Adjustment by Corridor One X",
  REVERSAL: "Reversal",
  EXPIRY: "Plan credits ended with the plan",
};

const RAZORPAY_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

function money(minor: number, currency: string): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(minor / 100);
}

/** Razorpay's hosted checkout, loaded only when a purchase needs it. */
function loadRazorpay(): Promise<boolean> {
  if (typeof window === "undefined") return Promise.resolve(false);
  if ((window as unknown as { Razorpay?: unknown }).Razorpay) return Promise.resolve(true);
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = RAZORPAY_SCRIPT;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

/**
 * Wallet & credits — the balance, what each paid action costs, what is on
 * sale, and every movement. Credits arrive when the payment processor
 * confirms a payment to the API; this page only opens the checkout and then
 * reloads the balance.
 */
export default function WalletPage() {
  const toast = useToast();
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [plans, setPlans] = useState<CreditPlan[]>([]);
  const [lines, setLines] = useState<LedgerLine[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [buying, setBuying] = useState<string | null>(null);
  const [pending, setPending] = useState<Purchase | null>(null);
  // One key per plan per visit: a double click or a retry reuses the order.
  const keys = useRef(new Map<string, string>());

  const load = useCallback(async () => {
    setError(null);
    try {
      const [w, p, l] = await Promise.all([api.getWallet(), api.listPlans(), api.getLedger(50)]);
      setWallet(w);
      setPlans(p);
      setLines(l.items);
      setTotal(l.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn’t load your wallet.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const buy = async (plan: CreditPlan) => {
    setBuying(plan.code);
    try {
      if (!keys.current.has(plan.code)) keys.current.set(plan.code, crypto.randomUUID());
      const purchase = await api.createPurchase(plan.code, keys.current.get(plan.code)!);
      setPending(purchase);
      if (purchase.provider !== "razorpay" || !(await loadRazorpay())) return;
      const Razorpay = (window as unknown as { Razorpay: new (o: object) => { open: () => void } }).Razorpay;
      new Razorpay({
        key: purchase.checkoutKey,
        order_id: purchase.providerOrderId,
        amount: purchase.amountMinor,
        currency: purchase.currency,
        name: "Corridor One X",
        description: `${plan.name} · ${plan.credits} credits`,
        handler: () => {
          keys.current.delete(plan.code);
          toast("Payment received. Your credits arrive in a moment.", "verified");
          window.setTimeout(() => void load(), 2500);
        },
      }).open();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Couldn’t open the checkout. Nothing was charged.");
    } finally {
      setBuying(null);
    }
  };

  return (
    <div className="pt-6 sm:pt-10">
      <header className="animate-rise">
        <p className="t-label text-fg-3">Account</p>
        <h1 className="t-large mt-2 text-fg">Wallet &amp; credits</h1>
        <p className="t-callout mt-2 max-w-xl text-fg-2">
          Credits pay for requests, unlocks and boosts. They never carry trade money.
        </p>
      </header>

      {error ? (
        <Notice tone="frozen" title="Couldn’t load" className="mt-8" action={<Button size="sm" variant="secondary" onClick={() => void load()}>Try again</Button>}>
          {error}
        </Notice>
      ) : null}

      <div className="mt-8 grid grid-cols-[minmax(0,1fr)] items-start gap-6 sm:mt-10 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-6">
          <Card as="section" className="rounded-[30px] p-6 sm:p-7" aria-label="Balance">
            {wallet ? (
              <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
                <div>
                  <p className="t-label text-fg-3">Balance</p>
                  <p className="t-hero mt-1 text-fg">
                    {wallet.balance}
                    <span className="t-title3 ml-2 text-fg-3">{wallet.balance === 1 ? "credit" : "credits"}</span>
                  </p>
                </div>
                <dl className="flex flex-wrap gap-x-8 gap-y-3">
                  <div>
                    <dt className="t-label text-fg-3">Plan</dt>
                    <dd className="t-headline mt-1 flex items-center gap-2 text-fg">
                      {wallet.plan ? (wallet.plan.name ?? wallet.plan.code) : "Free"}
                      {wallet.plan?.state === "grace" ? (
                        <Chip tone="move" size="sm" noIcon>
                          Ended · renew to keep it
                        </Chip>
                      ) : null}
                    </dd>
                    {wallet.plan ? (
                      <dd className="t-sub mt-0.5 text-fg-3">
                        {wallet.plan.state === "active" ? "Until" : "Ended"} {formatDay(wallet.plan.expiresAt)}
                        {wallet.plan.state === "active" && wallet.planCredits
                          ? ` · ${wallet.planCredits} plan credits end then`
                          : ""}
                      </dd>
                    ) : null}
                  </div>
                  <div>
                    <dt className="t-label text-fg-3">Free requests</dt>
                    <dd className="t-headline mt-1 text-fg">
                      {wallet.freeRfqs ? `${wallet.freeRfqs.remaining} of ${wallet.freeRfqs.allowance} left` : "After verification"}
                    </dd>
                  </div>
                </dl>
              </div>
            ) : (
              <Skeleton className="h-20 w-full rounded-[18px]" />
            )}
          </Card>

          <section aria-labelledby="buy-title">
            <h2 id="buy-title" className="t-title3 text-fg">
              Add credits
            </h2>
            {wallet && !wallet.checkoutAvailable ? (
              <Notice tone="info" className="mt-3">
                {wallet.freeRfqs === null
                  ? "Credits can be bought once your business is verified."
                  : "Buying credits opens soon. Your free requests work in the meantime."}
              </Notice>
            ) : null}
            <p className="t-sub mt-2 text-fg-3">
              Credits from a plan end when the plan does; top-up credits don’t expire.
            </p>
            {pending && pending.status === "created" ? (
              <Notice tone="move" title="Order opened" className="mt-3">
                {pending.credits} credits for {money(pending.amountMinor, pending.currency)}. They are added as soon
                as the payment is confirmed.
              </Notice>
            ) : null}
            <ul className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {plans.map((plan) => (
                <li key={plan.code} className="relief flex flex-col rounded-[24px] p-5">
                  <p className="t-label text-fg-3">{plan.kind === "plan" ? `${plan.periodDays} days` : "One-off"}</p>
                  <p className="t-title3 mt-1 text-fg">{plan.name}</p>
                  <p className="t-callout mt-1 text-fg-2">{plan.credits} credits</p>
                  <p className="t-headline mt-4 text-fg">{money(plan.priceMinor, plan.currency)}</p>
                  {plan.isPlaceholder ? <p className="t-foot text-fg-3">Price to be confirmed</p> : null}
                  <Button
                    variant="secondary"
                    className="mt-4"
                    block
                    loading={buying === plan.code}
                    disabled={!wallet?.checkoutAvailable || (buying !== null && buying !== plan.code)}
                    onClick={() => void buy(plan)}
                  >
                    Buy · {money(plan.priceMinor, plan.currency)}
                  </Button>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="ledger-title">
            <h2 id="ledger-title" className="t-title3 text-fg">
              Activity
            </h2>
            {lines === null ? (
              <Skeleton className="mt-4 h-24 w-full rounded-[22px]" />
            ) : lines.length === 0 ? (
              <EmptyState icon="vault" title="Nothing yet" className="mt-4">
                Purchases and what you spend credits on appear here.
              </EmptyState>
            ) : (
              <>
                <ul className="relief mt-4 divide-y divide-line rounded-[24px] px-5">
                  {lines.map((l) => (
                    <li key={l.id} className="flex items-center justify-between gap-4 py-3.5">
                      <div className="min-w-0">
                        <p className="t-body truncate text-fg">
                          {LINE_LABEL[l.entryType]}
                          {l.free ? <span className="t-sub ml-2 text-accent">Free</span> : null}
                        </p>
                        <p className="t-sub text-fg-3">{formatDay(l.createdAt)}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className={`t-code ${l.amount > 0 ? "text-accent" : "text-fg"}`}>
                          {l.amount > 0 ? `+${l.amount}` : l.amount}
                        </p>
                        <p className="t-foot text-fg-3">balance {l.balanceAfter}</p>
                      </div>
                    </li>
                  ))}
                </ul>
                {total > lines.length ? (
                  <p className="t-sub mt-3 text-fg-3">
                    Showing the latest {lines.length} of {total}.
                  </p>
                ) : null}
              </>
            )}
          </section>
        </div>

        <aside className="space-y-5 lg:sticky lg:top-24" aria-labelledby="prices-title">
          <div className="well rounded-[26px] p-5">
            <h2 id="prices-title" className="t-label text-fg-3">
              What things cost
            </h2>
            {wallet ? (
              <dl className="mt-3 space-y-2.5">
                {wallet.prices.map((p) => (
                  <div key={p.action} className="flex items-baseline justify-between gap-3">
                    <dt className="t-sub text-fg-2">{ACTION_LABEL[p.action]}</dt>
                    <dd className="t-code shrink-0 text-fg">
                      {p.credits}
                      {p.isPlaceholder ? <span className="text-fg-3"> *</span> : null}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : (
              <Skeleton className="mt-3 h-32 w-full rounded-[14px]" />
            )}
            {wallet?.prices.some((p) => p.isPlaceholder) ? (
              <p className="t-foot mt-3 text-fg-3">* To be confirmed. The price is shown on every button before you click.</p>
            ) : null}
          </div>
          <div className="relief rounded-[26px] p-5">
            <p className="t-label text-fg-3">On every paid button</p>
            <p className="t-sub mt-2 text-fg-2">The price and your balance are printed on the button itself:</p>
            <CreditButton wallet={wallet} action="OFFER_UNLOCK" onClick={() => toast("Offers arrive with requests for quotation.")} size="md" block className="mt-3">
              Unlock offer
            </CreditButton>
          </div>
        </aside>
      </div>
    </div>
  );
}
