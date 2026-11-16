import type { ReactNode } from "react";
import { countryName } from "@/components/account/countries";
import { Chip } from "@/components/ui/Chip";
import { formatDay } from "@/lib/verification";
import { paymentLabel, type RfqSellerView, type RfqTracking } from "@/lib/trade";

const OPERATOR = { MAX: "at most", MIN: "at least", EQ: "exactly" } as const;

const TRACKING: Record<RfqTracking, { label: string; tone: "verified" | "move" | "frozen" | "neutral" | "quiet" }> = {
  draft: { label: "Draft", tone: "quiet" },
  awaiting: { label: "Awaiting offers", tone: "move" },
  quoted: { label: "Offers in", tone: "verified" },
  expired: { label: "Expired", tone: "neutral" },
  rejected: { label: "Not accepted", tone: "frozen" },
  unmatched: { label: "No seller found", tone: "neutral" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

export function TrackingChip({ tracking }: { tracking: RfqTracking }) {
  const t = TRACKING[tracking] ?? TRACKING.awaiting;
  return (
    <Chip tone={t.tone} size="sm" noIcon>
      {t.label}
    </Chip>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line py-2.5 last:border-0">
      <dt className="t-sub shrink-0 text-fg-3">{label}</dt>
      <dd className="t-body min-w-0 text-right text-fg">{children}</dd>
    </div>
  );
}

/**
 * A request exactly as a matched seller reads it. The buyer's preview and the
 * seller's opened request render this same component from the same API shape,
 * so what the buyer checks is what the seller gets: a company code instead of
 * a name, and no target price.
 */
export function RequestSheet({ rfq }: { rfq: RfqSellerView }) {
  return (
    <div>
      <p className="t-code text-fg-3">
        {rfq.dealCode ?? "Not submitted yet"}
        {rfq.buyerCode ? ` · buyer ${rfq.buyerCode}` : ""}
      </p>
      <h3 className="t-title3 mt-1 break-words text-fg">{rfq.productName}</h3>
      <p className="t-sub mt-0.5 text-fg-3">
        {[rfq.category, rfq.variety, rfq.grade].filter(Boolean).join(" · ")}
      </p>
      <dl className="mt-4">
        <Row label="Quantity">{rfq.quantity ? `${Number(rfq.quantity)} ${rfq.unit}` : "Not set"}</Row>
        <Row label="Packaging">{rfq.packaging ?? "Not specified"}</Row>
        <Row label="Incoterms">{rfq.incoterms.length ? rfq.incoterms.join(", ") : "Not set"}</Row>
        <Row label="Payment">{rfq.paymentTerms ? paymentLabel(rfq.paymentTerms) : "Not set"}</Row>
        <Row label="Deliver to">
          {[rfq.destinationPort, rfq.deliveryCountry ? countryName(rfq.deliveryCountry) : null].filter(Boolean).join(", ") || "Not set"}
        </Row>
        <Row label="Delivery window">
          {rfq.deliveryFrom && rfq.deliveryTo ? `${formatDay(rfq.deliveryFrom)} to ${formatDay(rfq.deliveryTo)}` : "Not set"}
        </Row>
        {rfq.certificates.length ? <Row label="Certificates">{rfq.certificates.map((c) => c.name).join(", ")}</Row> : null}
      </dl>
      {rfq.specs.length ? (
        <>
          <p className="t-label mt-5 text-fg-3">Specifications</p>
          <dl className="mt-1">
            {rfq.specs.map((s) => (
              <Row key={s.parameterId} label={s.name}>
                <span className="t-code">
                  {OPERATOR[s.operator]} {s.value}
                  {s.unit ? ` ${s.unit}` : ""}
                </span>
              </Row>
            ))}
          </dl>
        </>
      ) : null}
      {rfq.notes ? (
        <>
          <p className="t-label mt-5 text-fg-3">Notes</p>
          <p className="t-body mt-1 whitespace-pre-line break-words text-fg-2">{rfq.notes}</p>
        </>
      ) : null}
    </div>
  );
}
