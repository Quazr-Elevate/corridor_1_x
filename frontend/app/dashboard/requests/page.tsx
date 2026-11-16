"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Wallet } from "@/lib/api";
import { trade, type MatchedRfqRow, type Rfq } from "@/lib/trade";
import { formatDay } from "@/lib/verification";
import { countryName } from "@/components/account/countries";
import { Button, LinkButton } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Controls";
import { CreditButton } from "@/components/ui/CreditButton";
import { EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { TrackingChip } from "@/components/trade/parts";

type Tab = "mine" | "matched";

/**
 * Requests — what this company has asked the market for, and what the trade
 * desk has matched to its listings. Opening a matched request costs credits
 * once; the button says how many before the click.
 */
export default function RequestsPage() {
  const router = useRouter();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("mine");
  const [mine, setMine] = useState<Rfq[] | null>(null);
  const [matched, setMatched] = useState<MatchedRfqRow[] | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [opening, setOpening] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [a, b, w] = await Promise.all([trade.listRfqs(), trade.listMatched(), api.getWallet()]);
      setMine(a.items);
      setMatched(b.items);
      setWallet(w);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn’t load your requests.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const open = async (row: MatchedRfqRow) => {
    setOpening(row.id);
    try {
      await trade.openMatched(row.id);
      router.push(`/dashboard/requests/matched/${row.id}`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Couldn’t open the request.");
      setOpening(null);
    }
  };

  return (
    <div className="pt-6 sm:pt-10">
      <header className="flex animate-rise flex-wrap items-end justify-between gap-4">
        <div>
          <p className="t-label text-fg-3">Trade</p>
          <h1 className="t-large mt-2 text-fg">Requests</h1>
          <p className="t-callout mt-2 max-w-xl text-fg-2">
            Ask the market for what you need, and answer requests matched to your listings.
          </p>
        </div>
        <LinkButton href="/dashboard/requests/new" variant="primary" icon="plus">
          New request
        </LinkButton>
      </header>

      <div className="mt-8">
        <Segmented<Tab>
          label="Which requests"
          value={tab}
          onChange={setTab}
          options={[
            { value: "mine", label: `Yours${mine ? ` · ${mine.length}` : ""}` },
            { value: "matched", label: `Matched to you${matched ? ` · ${matched.length}` : ""}` },
          ]}
        />
      </div>

      {error ? (
        <Notice tone="frozen" title="Couldn’t load" className="mt-6" action={<Button size="sm" variant="secondary" onClick={() => void load()}>Try again</Button>}>
          {error}
        </Notice>
      ) : null}

      {tab === "mine" ? (
        mine === null ? (
          <Skeleton className="mt-6 h-28 w-full rounded-[24px]" />
        ) : mine.length === 0 ? (
          <EmptyState icon="inbox" title="No requests yet" className="mt-6">
            Start one from a listing in the market, or describe what you need.
          </EmptyState>
        ) : (
          <ul className="mt-6 space-y-3">
            {mine.map((r) => (
              <li key={r.id}>
                <Link href={`/dashboard/requests/${r.id}`} className="relief flex flex-wrap items-center justify-between gap-3 rounded-[22px] px-5 py-4 transition-shadow hover:shadow-[var(--relief)]">
                  <div className="min-w-0">
                    <p className="t-code text-fg-3">{r.dealCode ?? "Draft"}</p>
                    <p className="t-headline truncate text-fg">{r.productName}</p>
                    <p className="t-sub text-fg-3">
                      {[r.category, r.quantity ? `${Number(r.quantity)} ${r.unit}` : null, r.deliveryCountry ? countryName(r.deliveryCountry) : null]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                  <TrackingChip tracking={r.tracking} />
                </Link>
              </li>
            ))}
          </ul>
        )
      ) : matched === null ? (
        <Skeleton className="mt-6 h-28 w-full rounded-[24px]" />
      ) : matched.length === 0 ? (
        <EmptyState icon="match" title="Nothing matched yet" className="mt-6">
          When a buyer’s request fits one of your published listings, Corridor One X sends it here.
        </EmptyState>
      ) : (
        <ul className="mt-6 space-y-3">
          {matched.map((r) => (
            <li key={r.id} className="relief flex flex-wrap items-center justify-between gap-4 rounded-[22px] px-5 py-4">
              <div className="min-w-0">
                <p className="t-headline truncate text-fg">{r.productName}</p>
                <p className="t-sub text-fg-3">
                  {[r.category, r.quantity ? `${Number(r.quantity)} ${r.unit}` : null, r.deliveryCountry ? countryName(r.deliveryCountry) : null]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <p className="t-foot mt-0.5 text-fg-3">
                  {r.deliveryTo ? `Deliver by ${formatDay(r.deliveryTo)}` : ""}
                  {r.expiresAt ? ` · closes ${formatDay(r.expiresAt)}` : ""}
                </p>
              </div>
              {r.opened ? (
                <LinkButton href={`/dashboard/requests/matched/${r.id}`} variant="secondary" iconRight="arrow-right">
                  Open
                </LinkButton>
              ) : (
                <CreditButton wallet={wallet} action="RFQ_VIEW" size="md" loading={opening === r.id} onClick={() => void open(r)}>
                  Open request
                </CreditButton>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
