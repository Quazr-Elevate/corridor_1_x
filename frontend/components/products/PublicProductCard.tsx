import Link from "next/link";
import { CheckCircle2, MapPin } from "lucide-react";
import type { PublicProductCard as Card } from "@/lib/publicApi";
import { photoUrl } from "@/lib/publicApi";

/**
 * Catalog card. Reused on /products and (later) the seller's own preview
 * of "how buyers see me". Deliberately minimal — no seller contact info.
 */
export function PublicProductCard({ product: p }: { product: Card }) {
  const photo = photoUrl(p.photo);
  const price = p.pricePerUnit ? `₹${p.pricePerUnit}/${p.unit}` : "On request";
  return (
    <Link
      href={`/products/${p.id}`}
      className="group relative flex flex-col overflow-hidden rounded-card border border-line-soft bg-ink-soft/60 transition-all hover:border-line hover:shadow-cta"
    >
      {/* Photo tile — 4:3, dark placeholder when the URL 404s */}
      <div className="relative aspect-[4/3] w-full overflow-hidden bg-ink-elevated">
        {photo ? (
          // Plain <img> — public backend photos change often; skipping next/image
          // avoids the loader config dance for now. Move to <Image> once we're
          // on a CDN.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={photo}
            alt={p.name}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs uppercase tracking-widest text-paper-muted/60">
            no photo
          </div>
        )}
        <span className="absolute left-2 top-2 chip !py-1">
          {p.category}
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-sm font-medium text-paper">{p.name}</h3>
          <span className="whitespace-nowrap text-sm font-semibold text-gradient">
            {price}
          </span>
        </div>

        {p.variety ? (
          <p className="text-xs text-paper-muted">
            {p.variety}
            {p.originState ? ` · ${p.originState}` : null}
          </p>
        ) : null}

        <div className="mt-auto flex items-center justify-between border-t border-line-soft pt-3 text-[11px] text-paper-muted">
          <span className="inline-flex items-center gap-1">
            <MapPin aria-hidden className="h-3 w-3 text-accent" />
            {p.seller.companyName}
            {p.seller.city ? ` · ${p.seller.city}` : ""}
          </span>
          <span
            aria-label="Verified seller"
            className="inline-flex items-center gap-1 text-accent"
          >
            <CheckCircle2 aria-hidden className="h-3 w-3" />
            Verified
          </span>
        </div>
      </div>
    </Link>
  );
}
