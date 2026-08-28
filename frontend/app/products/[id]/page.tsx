import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { AmbientBackground } from "@/components/brand/AmbientBackground";
import { ContactGate } from "@/components/products/ContactGate";
import { PhotoCarousel } from "@/components/products/PhotoCarousel";
import { PublicNav } from "@/components/products/PublicNav";
import { publicApi } from "@/lib/publicApi";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const p = await publicApi.getProduct(id);
    return {
      title: `${p.name} — Cor1x catalog`,
      description:
        p.description ||
        `${p.variety || p.category}, ${p.originState || "India"}. Listed by ${p.seller.companyName}.`,
    };
  } catch {
    return { title: "Product — Cor1x" };
  }
}

export default async function ProductDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let product;
  try {
    product = await publicApi.getProduct(id);
  } catch {
    notFound();
  }

  const specs: Array<{ label: string; value: string | null }> = [
    { label: "Category", value: product.category },
    { label: "Variety", value: product.variety },
    { label: "Origin", value: product.originState },
    { label: "Packaging", value: product.packaging },
    {
      label: "Available",
      value: product.quantity ? `${product.quantity} ${product.unit}` : null,
    },
    { label: "MOQ", value: product.moq ? `${product.moq} ${product.unit}` : null },
    {
      label: "Price",
      value: product.pricePerUnit
        ? `₹${product.pricePerUnit} / ${product.unit}`
        : "On request",
    },
  ];

  return (
    <main className="relative min-h-screen overflow-hidden bg-ink text-paper">
      <AmbientBackground />

      <div className="relative mx-auto max-w-5xl px-5 py-8">
        <PublicNav />

        <Link
          href="/products"
          className="mt-8 inline-flex items-center gap-1 text-xs text-paper-muted transition-colors hover:text-paper enter"
          data-delay="2"
        >
          <ArrowLeft className="h-3 w-3" aria-hidden />
          Back to catalog
        </Link>

        <div className="mt-4 grid gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <section className="enter" data-delay="3">
            <PhotoCarousel photos={product.photos} alt={product.name} />
          </section>

          <section className="space-y-6 enter" data-delay="4">
            <div>
              <p className="chip">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
                {product.category}
              </p>
              <h1 className="mt-3 text-display text-paper">{product.name}</h1>
              {product.variety && (
                <p className="mt-1 text-sm text-paper-muted">{product.variety}</p>
              )}
            </div>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-card border border-line-soft bg-ink-soft/60 p-4">
              {specs
                .filter((s) => s.value)
                .map((s) => (
                  <div key={s.label}>
                    <dt className="text-[10px] uppercase tracking-widest text-paper-muted">
                      {s.label}
                    </dt>
                    <dd className="mt-1 text-sm text-paper">{s.value}</dd>
                  </div>
                ))}
            </dl>

            {product.description && (
              <div>
                <h2 className="text-title text-paper">About this lot</h2>
                <p className="mt-2 text-sm leading-relaxed text-paper-muted">
                  {product.description}
                </p>
              </div>
            )}

            {/* Seller mini-card — no contact info, just identity + trust pill */}
            <div className="rounded-card border border-line-soft bg-ink-soft/60 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-paper-muted">
                    Listed by
                  </p>
                  <p className="mt-1 text-sm font-medium text-paper">
                    {product.seller.companyName}
                  </p>
                  {(product.seller.city || product.seller.state) && (
                    <p className="text-xs text-paper-muted">
                      {[product.seller.city, product.seller.state]
                        .filter(Boolean)
                        .join(", ")}
                    </p>
                  )}
                </div>
                <span className="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2.5 py-1 text-[11px] font-medium text-accent ring-1 ring-inset ring-accent/30">
                  <CheckCircle2 aria-hidden className="h-3 w-3" />
                  Verified
                </span>
              </div>
            </div>

            <ContactGate productId={product.id} productName={product.name} />
          </section>
        </div>

        <footer className="mt-16 border-t border-line-soft pt-6 text-xs text-paper-muted">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>© 2026 Corridor One X</span>
            <div className="flex items-center gap-4">
              <a href="/privacy" className="hover:text-paper">Privacy</a>
              <a href="/terms" className="hover:text-paper">Terms</a>
              <a href="mailto:privacy@cor1x.com" className="hover:text-paper">Grievance</a>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
