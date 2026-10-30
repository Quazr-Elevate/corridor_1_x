import Link from "next/link";
import { assetUrl, type Me } from "@/lib/api";
import { MEDIA } from "@/lib/media";
import { PASSPORT_PATH, statusMeta } from "@/lib/verification";
import { Photo } from "@/components/art/Photo";
import { Chip } from "@/components/ui/Chip";
import { Icon } from "@/components/ui/Icon";
import { countryName } from "@/components/account/countries";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "—";
}

/**
 * The business's own hero on the trader home — their banner (or a port
 * photo until they upload one), their logo, company name and verification
 * state — so the workspace reads like the business's own site.
 */
export function BusinessHero({ me }: { me: Me }) {
  const name = me.business.legalName || me.businessName || "Your company";
  const banner = me.branding?.bannerUrl ? assetUrl(me.branding.bannerUrl) : null;
  const logo = me.branding?.logoUrl ? assetUrl(me.branding.logoUrl) : null;
  const meta = statusMeta(me.verification.status);
  const place = [me.business.city, countryName(me.business.country)].filter(Boolean).join(", ");
  const verified = me.verification.status === "verified";

  const inner = (
    <>
      <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-ink/85 via-ink/35 to-ink/10" />
      <div className="absolute inset-x-5 bottom-5 flex items-end justify-between gap-4 sm:inset-x-7 sm:bottom-6">
        <div className="flex min-w-0 items-center gap-4">
          <span className="grid size-16 shrink-0 place-items-center overflow-hidden rounded-[20px] bg-cream text-ink shadow-[0_8px_24px_rgb(0_0_0/0.3)] sm:size-20">
            {logo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={logo} alt={`${name} logo`} className="size-full object-cover" />
            ) : (
              <span className="t-title2">{initials(name)}</span>
            )}
          </span>
          <div className="min-w-0">
            <p className="t-title1 truncate text-cream">{name}</p>
            <p className="t-sub mt-1 flex flex-wrap items-center gap-2 text-cream/75">
              {verified ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-lime px-2 py-0.5 text-[12px] font-medium text-ink">
                  <Icon name="check" size={12} /> Verified business
                </span>
              ) : (
                <Chip tone={meta.tone} size="sm" className={meta.tone === "neutral" ? "bg-cream/90 text-ink/75 shadow-none" : undefined}>
                  {meta.tone === "neutral" ? "Not verified yet" : meta.label}
                </Chip>
              )}
              {place ? <span className="truncate">{place}</span> : null}
            </p>
          </div>
        </div>
        <Link
          href={PASSPORT_PATH}
          className="glass hidden shrink-0 items-center gap-1.5 rounded-full px-3.5 py-2 text-[13px] font-medium text-fg sm:inline-flex"
        >
          <Icon name="pen" size={14} /> Edit profile
        </Link>
      </div>
    </>
  );

  return (
    <section aria-label="Your business" className="relative isolate h-[200px] overflow-hidden rounded-[30px] sm:h-[240px]">
      {banner ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={banner} alt="" className="absolute inset-0 size-full object-cover" />
          {inner}
        </>
      ) : (
        <Photo media={MEDIA.portDay} decorative fill objectPosition="50% 60%" sizes="100vw" className="absolute inset-0">
          {inner}
        </Photo>
      )}
    </section>
  );
}
