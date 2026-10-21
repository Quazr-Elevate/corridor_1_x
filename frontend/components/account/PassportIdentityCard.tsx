"use client";

import { entityTypeShort, type Me, type VerificationDoc } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDay, verificationCounts } from "@/lib/verification";
import { Icon, type IconName } from "@/components/ui/Icon";
import { SolidPanel } from "@/components/ui/Surface";
import { dot, memberCode, memberSince, roleLabel } from "@/components/trader/format";
import { countryName } from "./countries";

export type PassportView = "self" | "counterparty";

/**
 * The dark identity card at the top of the Passport (reference: portal
 * /passport). Solid ink with a lime glow; lime only on the label and the
 * Verified state.
 *
 *   self          your company, role, place, member since; status,
 *                 fields and documents
 *   counterparty  what a buyer sees: role and region, the name frosted
 *                 (decoy glyphs — the real name never reaches this DOM),
 *                 the badge, and that contact opens only on reveal
 */
export function PassportIdentityCard({
  me,
  docs,
  docsLoading,
  view,
}: {
  me: Me;
  docs: VerificationDoc[];
  docsLoading: boolean;
  view: PassportView;
}) {
  const v = me.verification;
  const { filled, total } = verificationCounts(v);
  const verified = v.status === "verified";
  const country = countryName(me.business.country) || countryName(me.business.operatingCountries?.[0]) || "";
  const name = me.businessName || me.business.legalName;
  const role = roleLabel(me);
  const place = [me.business.city, me.business.state].filter(Boolean).join(", ");
  const region = me.business.state || country || "India";
  const approved = docs.filter((d) => d.status === "approved").length;
  const counterparty = view === "counterparty";

  const status: { icon: IconName; label: string; cls: string } =
    v.status === "verified"
      ? { icon: "shield", label: "Verified", cls: "text-accent" }
      : v.status === "pending_verification"
        ? { icon: "clock", label: "In review", cls: "text-amber" }
        : v.status === "rejected"
          ? { icon: "alert", label: "Needs changes", cls: "text-danger" }
          : { icon: "passport", label: "Not yet sent", cls: "text-fg-2" };

  return (
    <SolidPanel className="rounded-[34px] p-7 sm:p-9">
      <section aria-label={counterparty ? "Your passport as counterparties see it" : "Your passport"}>
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-32 -left-20 size-96 rounded-full bg-lime/[0.12] blur-3xl"
        />
        <div className="relative flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <p className="t-label text-lime">Corridor Passport{country ? ` · ${country}` : ""}</p>
            {counterparty ? (
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <h2 className="t-title1 text-cream">
                  {role} · {region}
                </h2>
                <span className="frost inline-flex h-6 w-[170px] items-center px-2.5" role="img" aria-label="Company name hidden">
                  <span className="frost-glyphs t-sub truncate font-medium text-cream" aria-hidden="true">
                    Verified Trading Co
                  </span>
                </span>
              </div>
            ) : (
              <h2 className={cn("t-title1 mt-3 break-words", name ? "text-cream" : "text-cream/30")}>
                {name || "Your company"}
              </h2>
            )}
            <p className="t-callout mt-2 text-cream/60">
              {counterparty
                ? dot(role, region, memberSince(me.emailVerifiedAt))
                : dot(role, entityTypeShort(me.business.entityType), place, memberSince(me.emailVerifiedAt))}
            </p>
          </div>
          <div className="sm:text-right">
            {counterparty ? (
              <>
                <p className="t-label text-cream/50">On lots as</p>
                <p className="t-headline mt-1.5 text-cream">{verified ? "Verified seller" : "Not listed yet"}</p>
              </>
            ) : (
              <>
                <p className="t-label text-cream/50">Member ID</p>
                <p className="t-code mt-1 text-[22px] text-cream">{memberCode(me.userId)}</p>
              </>
            )}
          </div>
        </div>

        <dl className="relative mt-8 grid grid-cols-3 gap-4 border-t border-cream/10 pt-6 sm:gap-6">
          <div className="min-w-0">
            <dt className="t-label text-cream/50">Status</dt>
            <dd className={cn("t-headline mt-1.5 flex items-center gap-1.5", status.cls)}>
              <Icon name={status.icon} size={15} className="shrink-0" />
              <span className="min-w-0">{status.label}</span>
            </dd>
          </div>
          {counterparty ? (
            <>
              <div className="min-w-0">
                <dt className="t-label text-cream/50">Location</dt>
                <dd className="t-headline mt-1.5 truncate text-cream" title={place || region}>
                  {place || region}
                </dd>
              </div>
              <div className="min-w-0">
                <dt className="t-label text-cream/50">Contact</dt>
                <dd className="t-headline mt-1.5 flex items-center gap-1.5 text-cream">
                  <Icon name="lock" size={15} className="shrink-0 text-cream/60" />
                  On reveal
                </dd>
              </div>
            </>
          ) : (
            <>
              <div className="min-w-0">
                <dt className="t-label text-cream/50">Fields</dt>
                <dd className="tabular mt-1.5 text-[20px] font-medium leading-tight text-cream">
                  {filled}/{total}
                </dd>
              </div>
              <div className="min-w-0">
                <dt className="t-label text-cream/50">Documents</dt>
                <dd className="tabular mt-1.5 text-[20px] font-medium leading-tight text-cream">
                  {docsLoading ? (
                    <span className="text-cream/40">—</span>
                  ) : (
                    <>
                      {docs.length}
                      <span className="t-foot mt-0.5 block font-normal text-cream/50">{approved} approved</span>
                    </>
                  )}
                </dd>
              </div>
            </>
          )}
        </dl>
        {!counterparty && verified && v.verifiedAt ? (
          <p className="t-foot relative mt-5 text-cream/50">Verified {formatDay(v.verifiedAt)}</p>
        ) : null}
      </section>
    </SolidPanel>
  );
}
