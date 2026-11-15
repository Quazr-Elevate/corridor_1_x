import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { LinkButton } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ReadField } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { EmptyState } from "@/components/ui/Surface";
import { MarketAmbient } from "@/components/market/MarketAmbient";
import { ApproxPrice } from "@/components/fx/FxContext";
import { CertificateLinks } from "@/components/products/CertificateLinks";
import { ContactGate } from "@/components/products/ContactGate";
import { PhotoCarousel } from "@/components/products/PhotoCarousel";
import { formatQty, joinDot, listingCode, packingLabel, priceRangeFigure, specValue } from "@/components/products/format";
import { commodityPhoto, MEDIA } from "@/lib/media";
import { publicApi, PublicApiError, type PublicProductDetail } from "@/lib/publicApi";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  try {
    const p = await publicApi.getProduct(id);
    return {
      title: `${p.name} — Corridor One X`,
      description:
        p.description?.slice(0, 160) ||
        `${joinDot(p.variety || p.category, p.originState || "India")}. From a seller verified by Corridor ops.`,
    };
  } catch {
    return { title: "Lot — Corridor One X" };
  }
}

/**
 * A lot, as a buyer sees it: the gallery, the figures and spec, and the
 * seller — frosted, because the API masks who it is until a verified
 * buyer reveals the contact.
 */
export default async function ProductDetailPage({ params }: Params) {
  const { id } = await params;
  let product: PublicProductDetail;
  try {
    // The visitor's cookie decides whether the price range comes back.
    product = await publicApi.getProduct(id, { cookie: (await cookies()).toString() });
  } catch (err) {
    if (err instanceof PublicApiError && (err.status === 404 || err.status === 422)) notFound();
    return (
      <div>
        <BackLink />
        <div className="relief mt-6 rounded-[30px]">
          <EmptyState
            icon="alert"
            title="We couldn’t load this lot"
            action={
              <LinkButton href={`/products/${encodeURIComponent(id)}`} variant="secondary">
                Try again
              </LinkButton>
            }
          >
            {err instanceof Error ? err.message : "Please try again in a moment."}
          </EmptyState>
        </div>
      </div>
    );
  }

  const p = product;
  const photos = p.photos.length ? p.photos : p.photo ? [p.photo] : [];
  const sellerPlace = p.seller.state || null;
  const volume = formatQty(p.quantity, p.unit);
  const moq = formatQty(p.moq, p.unit);
  const priced = p.priceVisible && p.priceMin !== null && p.priceMin !== "";
  const capacity = formatQty(p.capacityPerMonth, p.capacityUnit || p.unit);
  const facts: Array<{ label: string; value: string | null }> = [
    { label: "Category", value: p.category },
    { label: "Grade", value: p.grade || p.variety },
    { label: "Origin", value: joinDot(p.originState, p.originCountry) || null },
    { label: "Packaging", value: p.packaging },
    { label: "Monthly capacity", value: capacity },
    { label: "Incoterms", value: p.incoterms.length ? p.incoterms.join(" · ") : null },
  ];

  return (
    <div className="relative isolate">
      <MarketAmbient media={commodityPhoto(p.category) ?? MEDIA.warehouse} opacity={0.22} />

      <BackLink />

      <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:items-start lg:gap-x-10">
        <div className="min-w-0 animate-rise lg:col-start-1 lg:row-start-1">
          <PhotoCarousel photos={photos} alt={p.name} category={p.category} />
        </div>

        <div className="min-w-0 space-y-6 lg:col-start-2 lg:row-span-3 lg:row-start-1">
          <header className="animate-rise" style={{ animationDelay: "60ms" }}>
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone="neutral" noIcon>
                {p.category}
              </Chip>
              <Chip tone="verified">Verified seller</Chip>
              <span className="t-code ml-auto text-fg-3">{listingCode(p.id)}</span>
            </div>
            <h1 className="t-large mt-4 break-words text-fg">{p.name}</h1>
            <p className="t-body mt-2 text-fg-2">
              {joinDot(
                p.grade || p.variety || p.category,
                p.originState ? `from ${p.originState}` : "India",
                packingLabel(p.packaging),
              )}
            </p>
          </header>

          <section
            aria-label="Price and volume"
            className="relief animate-rise rounded-[30px] p-6"
            style={{ animationDelay: "120ms" }}
          >
            <p className="t-label text-fg-3">Price</p>
            <p className={`t-title1 tabular mt-1.5 ${priced ? "text-fg" : "text-fg-3"}`}>
              {priceRangeFigure(p.priceMin, p.priceMax, p.unit, p.currency)}
              {priced ? <ApproxPrice amount={p.priceMin} currency={p.currency} /> : null}
            </p>
            {!p.priceVisible ? (
              <p className="t-sub mt-1 text-fg-3">
                The price range is shown to signed-in, verified businesses.
              </p>
            ) : !priced ? (
              <p className="t-sub mt-1 text-fg-3">The seller quotes on request.</p>
            ) : p.priceValidUntil ? (
              <p className="t-sub mt-1 text-fg-3">Indicative range, valid until {p.priceValidUntil}.</p>
            ) : null}

            <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-line pt-4">
              <Figure label="Volume" value={volume} />
              <Figure label="Minimum order" value={moq} />
            </dl>

            <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-5 border-t border-line pt-5">
              {facts.map((s) => (
                <ReadField key={s.label} label={s.label} value={s.value} />
              ))}
            </div>
          </section>

          <div className="animate-rise" style={{ animationDelay: "180ms" }}>
            <ContactGate productId={p.id} sellerId={p.seller.sellerId} sellerPlace={sellerPlace} />
          </div>
        </div>

        {p.specs.length || p.certificates.length ? (
          <section
            className="relief min-w-0 animate-rise rounded-[30px] p-6 sm:p-8 lg:col-start-1"
            style={{ animationDelay: "150ms" }}
            aria-labelledby="lot-specs"
          >
            {p.specs.length ? (
              <>
                <p className="t-label text-fg-3">Stated by the seller</p>
                <h2 id="lot-specs" className="t-title3 mt-1.5 text-fg">
                  Specifications
                </h2>
                <dl className="mt-4 divide-y divide-line">
                  {p.specs.map((s) => (
                    <div key={s.parameterId} className="flex items-baseline justify-between gap-4 py-2.5">
                      <dt className="t-body min-w-0 text-fg-2">
                        {s.name}
                        {s.testMethod ? <span className="t-foot ml-2 text-fg-3">{s.testMethod}</span> : null}
                      </dt>
                      <dd className="t-code tabular shrink-0 text-fg">{specValue(s.value, s.unit, s.operator)}</dd>
                    </div>
                  ))}
                </dl>
              </>
            ) : null}
            {p.certificates.length ? (
              <div className={p.specs.length ? "mt-7 border-t border-line pt-6" : undefined}>
                <p className="t-label text-fg-3">Checked by Corridor ops</p>
                <h2 id={p.specs.length ? undefined : "lot-specs"} className="t-title3 mt-1.5 text-fg">
                  Documents
                </h2>
                <CertificateLinks certificates={p.certificates} />
              </div>
            ) : null}
          </section>
        ) : null}

        {p.description ? (
          <section
            className="relief min-w-0 animate-rise rounded-[30px] p-6 sm:p-8 lg:col-start-1"
            style={{ animationDelay: "120ms" }}
            aria-labelledby="about-lot"
          >
            <p className="t-label text-fg-3">From the seller</p>
            <h2 id="about-lot" className="t-title3 mt-1.5 text-fg">
              About this lot
            </h2>
            <p className="t-body mt-3 whitespace-pre-line break-words text-fg-2">{p.description}</p>
          </section>
        ) : null}
      </div>
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="min-w-0">
      <dt className="t-label text-fg-3">{label}</dt>
      <dd
        className={`tabular mt-1 truncate text-[20px] font-medium leading-tight tracking-[-0.025em] ${value ? "text-fg" : "text-fg-3"}`}
      >
        {value ?? "—"}
      </dd>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/products"
      className="t-callout inline-flex items-center gap-1.5 rounded-full py-1 pr-2 text-fg-2 transition-colors hover:text-fg"
    >
      <Icon name="arrow-left" size={16} />
      The market
    </Link>
  );
}
