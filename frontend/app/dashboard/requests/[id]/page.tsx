"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Wallet } from "@/lib/api";
import { money, paymentLabel, trade, type DealChat as Chat, type Offer, type Rfq } from "@/lib/trade";
import { formatDay } from "@/lib/verification";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { CreditButton } from "@/components/ui/CreditButton";
import { Icon } from "@/components/ui/Icon";
import { Card, EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { RfqForm } from "@/components/trade/RfqForm";
import { RequestSheet, TrackingChip } from "@/components/trade/parts";
import { DealChat } from "@/components/trade/DealChat";
import { DealCounters } from "@/components/trade/DealCounters";
import { DealSamples } from "@/components/trade/DealSamples";
import { DealTermSheet } from "@/components/trade/DealTermSheet";
import { DealDocuments } from "@/components/trade/DealDocuments";
import { DealPayments } from "@/components/trade/DealPayments";
import { HoldButton } from "@/components/ui/Controls";

/**
 * One request. While it is a draft this is the editor; once submitted it is
 * the request as sent, its status, and the offers that came back. An offer's
 * price opens with credits; the button prints the cost first.
 */
export default function RequestPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const [rfq, setRfq] = useState<Rfq | null>(null);
  const [offers, setOffers] = useState<Offer[] | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unlocking, setUnlocking] = useState<string | null>(null);
  const [choosing, setChoosing] = useState<string | null>(null);
  // The deal's chat once the buyer has chosen an offer; null before (404).
  const [chat, setChat] = useState<Chat | null>(null);

  const loadOffers = useCallback(async () => {
    const [o, w] = await Promise.all([trade.listOffers(id), api.getWallet()]);
    setOffers(o.items);
    setWallet(w);
  }, [id]);

  const loadChat = useCallback(async (dealCode: string | null) => {
    if (!dealCode) return;
    try {
      setChat(await trade.dealChat(dealCode));
    } catch {
      setChat(null);
    }
  }, []);

  useEffect(() => {
    let live = true;
    trade
      .getRfq(id)
      .then((r) => {
        if (!live) return;
        setRfq(r);
        if (r.status !== "draft") {
          void loadOffers().catch(() => undefined);
          void loadChat(r.dealCode);
        }
      })
      .catch((err) => live && setError(err instanceof ApiError && err.status === 404 ? "This request doesn’t exist." : "Couldn’t load the request."));
    return () => {
      live = false;
    };
  }, [id, loadOffers, loadChat]);

  const choose = async (offer: Offer) => {
    if (!rfq?.dealCode) return;
    setChoosing(offer.id);
    try {
      await trade.chooseOffer(rfq.dealCode, offer.id);
      toast("Offer chosen. Negotiation is open.", "verified");
      await Promise.all([loadOffers(), loadChat(rfq.dealCode)]);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Couldn’t choose the offer.");
    } finally {
      setChoosing(null);
    }
  };

  const unlock = async (offer: Offer) => {
    setUnlocking(offer.id);
    try {
      await trade.unlockOffer(offer.id);
      await loadOffers();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Couldn’t unlock the offer.");
    } finally {
      setUnlocking(null);
    }
  };

  const remove = async () => {
    if (!rfq) return;
    try {
      await trade.deleteRfq(rfq.id);
      router.replace("/dashboard/requests");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Couldn’t delete the draft.");
    }
  };

  return (
    <div className="pt-6 sm:pt-10">
      <Link href="/dashboard/requests" className="t-sub inline-flex items-center gap-1.5 text-fg-3 hover:text-fg">
        <Icon name="arrow-left" size={15} />
        Requests
      </Link>
      {error ? (
        <Notice tone="frozen" className="mt-6">{error}</Notice>
      ) : !rfq ? (
        <Skeleton className="mt-6 h-64 w-full rounded-[26px]" />
      ) : (
        <>
          <header className="mt-4 flex animate-rise flex-wrap items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="t-code text-fg-3">{rfq.dealCode ?? "Draft request"}</p>
              <h1 className="t-large mt-1 break-words text-fg">{rfq.productName}</h1>
            </div>
            <div className="flex items-center gap-3">
              <TrackingChip tracking={rfq.tracking} />
              {rfq.status === "draft" ? (
                <Button variant="danger" size="sm" onClick={() => void remove()}>
                  Delete draft
                </Button>
              ) : null}
            </div>
          </header>

          {rfq.status === "draft" ? (
            <RfqForm
              rfq={rfq}
              onChange={setRfq}
              onSubmitted={(r) => {
                setRfq(r);
                void loadOffers().catch(() => undefined);
              }}
            />
          ) : (
            <div className="mt-8 grid grid-cols-[minmax(0,1fr)] items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
              <section aria-labelledby="offers-title" className="min-w-0 space-y-6">
                {chat ? <DealChat chat={chat} /> : null}
                {chat ? (
                  <DealCounters
                    dealCode={chat.dealCode}
                    canWrite={chat.canWrite}
                    currency={offers?.find((o) => o.status === "published" && o.unlocked)?.currency ?? null}
                  />
                ) : null}
                {chat ? <DealPayments dealCode={chat.dealCode} side="buyer" /> : null}
                {chat ? <DealDocuments dealCode={chat.dealCode} canWrite={!chat.suspended} /> : null}
                {chat ? <DealTermSheet dealCode={chat.dealCode} canWrite={chat.canWrite} /> : null}
                {chat ? <DealSamples dealCode={chat.dealCode} side="buyer" canWrite={chat.canWrite} /> : null}
                <div>
                <h2 id="offers-title" className="t-title3 text-fg">
                  Offers
                </h2>
                {rfq.tracking === "rejected" && rfq.rejectionReason ? (
                  <Notice tone="frozen" title="Corridor One X could not take this request" className="mt-3">
                    {rfq.rejectionReason} Your credit was returned.
                  </Notice>
                ) : rfq.tracking === "unmatched" ? (
                  <Notice tone="info" title="No seller fits this request" className="mt-3">
                    Your credit was returned. Try wider limits or a later delivery window.
                  </Notice>
                ) : null}
                {offers === null ? (
                  <Skeleton className="mt-4 h-28 w-full rounded-[24px]" />
                ) : offers.length === 0 ? (
                  <EmptyState icon="inbox" title={rfq.tracking === "awaiting" ? "No offers yet" : "No offers"} className="mt-4">
                    {rfq.tracking === "awaiting"
                      ? `Corridor One X is matching sellers. This request stays open until ${rfq.expiresAt ? formatDay(rfq.expiresAt) : "it closes"}.`
                      : "This request is closed."}
                  </EmptyState>
                ) : (
                  <ul className="mt-4 grid gap-4 sm:grid-cols-2">
                    {offers.map((o) => (
                      <li key={o.id}>
                        <Card className="flex h-full flex-col rounded-[24px] p-5">
                          <div className="flex items-center justify-between gap-2">
                            <p className="t-code text-fg-2">{o.sellerCode ?? "Verified seller"}</p>
                            {o.status === "expired" ? (
                              <Chip tone="neutral" size="sm" noIcon>
                                Expired
                              </Chip>
                            ) : o.status === "not_chosen" ? (
                              <Chip tone="neutral" size="sm" noIcon>
                                Not chosen
                              </Chip>
                            ) : chat && o.status === "published" ? (
                              <Chip tone="verified" size="sm" noIcon>
                                Chosen
                              </Chip>
                            ) : null}
                          </div>
                          <p className="t-title2 mt-3 text-fg">{o.unlocked ? money(o.priceMinor, o.currency) : "Price locked"}</p>
                          <p className="t-sub text-fg-3">{o.unlocked ? `per ${o.unit} · ${Number(o.quantity)} ${o.unit} offered` : "Unlock to see the price and terms"}</p>
                          <dl className="mt-4 space-y-1.5">
                            <div className="flex justify-between gap-3">
                              <dt className="t-sub text-fg-3">Specifications met</dt>
                              <dd className="t-code text-fg">
                                {o.specsMet} of {o.specsTotal}
                              </dd>
                            </div>
                            <div className="flex justify-between gap-3">
                              <dt className="t-sub text-fg-3">Lead time</dt>
                              <dd className="t-code text-fg">{o.leadTimeDays} days</dd>
                            </div>
                            <div className="flex justify-between gap-3">
                              <dt className="t-sub text-fg-3">Incoterm</dt>
                              <dd className="t-code text-fg">{o.incoterm}</dd>
                            </div>
                            {o.unlocked ? (
                              <>
                                <div className="flex justify-between gap-3">
                                  <dt className="t-sub text-fg-3">Port of loading</dt>
                                  <dd className="t-sub text-fg">{o.portOfLoading ?? "Not stated"}</dd>
                                </div>
                                <div className="flex justify-between gap-3">
                                  <dt className="t-sub shrink-0 text-fg-3">Payment</dt>
                                  <dd className="t-sub text-right text-fg">{(o.paymentTerms ?? []).map(paymentLabel).join(", ")}</dd>
                                </div>
                              </>
                            ) : null}
                            <div className="flex justify-between gap-3">
                              <dt className="t-sub text-fg-3">Valid until</dt>
                              <dd className="t-sub text-fg">{formatDay(o.validUntil)}</dd>
                            </div>
                          </dl>
                          {!o.unlocked && o.status === "published" && !chat ? (
                            <CreditButton wallet={wallet} action="OFFER_UNLOCK" size="md" block className="mt-5" loading={unlocking === o.id} onClick={() => void unlock(o)}>
                              Unlock offer
                            </CreditButton>
                          ) : o.unlocked && o.status === "published" && !chat ? (
                            <div className="mt-5">
                              <HoldButton tone="commit" icon="check" onCommit={() => void choose(o)} loading={choosing === o.id}>
                                Choose this offer
                              </HoldButton>
                              <p className="t-sub mt-2 text-fg-3">Opens negotiation with this seller; the other offers close.</p>
                            </div>
                          ) : null}
                        </Card>
                      </li>
                    ))}
                  </ul>
                )}
                </div>
              </section>
              <aside className="relief rounded-[26px] p-5 lg:sticky lg:top-24" aria-label="Your request">
                <p className="t-label text-fg-3">Your request, as sellers see it</p>
                <div className="mt-3">
                  <RequestSheet rfq={rfq} />
                </div>
                {rfq.targetPriceMin !== null ? (
                  <p className="t-sub mt-4 text-fg-3">
                    Your target, seen by Corridor One X only: {money(rfq.targetPriceMin, rfq.currency)}
                    {rfq.targetPriceMax !== null ? ` to ${money(rfq.targetPriceMax, rfq.currency)}` : ""} per {rfq.unit}.
                  </p>
                ) : null}
              </aside>
            </div>
          )}
        </>
      )}
    </div>
  );
}
