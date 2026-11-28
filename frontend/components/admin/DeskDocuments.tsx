"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, errorMessage, type ContractTemplate, type ContractTerms, type DeskDocument } from "@/lib/adminApi";
import { fromMinor, money, toMinor } from "@/lib/trade";
import { formatDay } from "@/lib/verification";
import { Button } from "@/components/ui/Button";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { Checkbox, HoldButton } from "@/components/ui/Controls";
import { Input, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { RejectSheet } from "@/components/admin/RejectSheet";
import { fmtAgo } from "@/components/admin/format";

const STATUS: Record<DeskDocument["status"], { label: string; tone: ChipTone }> = {
  issued: { label: "With the party", tone: "move" },
  party_signed: { label: "Countersign", tone: "move" },
  signed: { label: "Signed", tone: "verified" },
  effective: { label: "In effect", tone: "verified" },
  void: { label: "Void", tone: "neutral" },
};
const KIND = { loi: "LOI", contract: "Contract" } as const;

const BLANK: ContractTerms = {
  tolerancePct: "5", shipmentFrom: "", shipmentTo: "", inspectionAgency: "", inspectionPoint: "Port of loading",
  latePenaltyPct: "2", qualityPenaltyPct: "1", claimWindowDays: 30, governingLaw: "", seat: "", forceMajeure: "",
};
const FIELDS: ReadonlyArray<{ key: keyof ContractTerms; label: string; type?: string; mono?: boolean }> = [
  { key: "tolerancePct", label: "Quantity tolerance %", mono: true },
  { key: "shipmentFrom", label: "Shipment from", type: "date" },
  { key: "shipmentTo", label: "Shipment to", type: "date" },
  { key: "inspectionAgency", label: "Inspection agency" },
  { key: "inspectionPoint", label: "Inspection point" },
  { key: "latePenaltyPct", label: "Late-delivery penalty %", mono: true },
  { key: "qualityPenaltyPct", label: "Quality penalty %", mono: true },
  { key: "claimWindowDays", label: "Claim window (days)", mono: true },
  { key: "governingLaw", label: "Governing law" },
  { key: "seat", label: "Arbitration seat" },
  { key: "forceMajeure", label: "Force majeure clause" },
];

const intOrNull = (v: string) => (v.trim() === "" ? null : Number.isFinite(Number(v)) ? Math.trunc(Number(v)) : null);

function TermsForm({ title, value, onChange }: { title: string; value: ContractTerms; onChange: (v: ContractTerms) => void }) {
  return (
    <fieldset className="well space-y-3 rounded-[18px] p-4">
      <legend className="t-label px-1 text-fg-3">{title}</legend>
      {FIELDS.map((f) => (
        <Input
          key={f.key}
          label={f.label}
          type={f.type}
          value={String(value[f.key] ?? "")}
          inputMode={f.mono ? "decimal" : undefined}
          inputClassName={f.mono ? "t-code" : undefined}
          onChange={(e) => onChange({ ...value, [f.key]: f.key === "claimWindowDays" ? Number(e.target.value) || 0 : e.target.value })}
        />
      ))}
      <p className="t-label pt-2 text-fg-3">Payment (as the payment terms need)</p>
      <div className="grid grid-cols-2 gap-3">
        <Input label="Advance %" optional inputMode="numeric" value={value.advancePct ?? ""} hint="Advance + balance terms."
          onChange={(e) => onChange({ ...value, advancePct: intOrNull(e.target.value) })} inputClassName="t-code" />
        <Input label="Credit period (days)" optional inputMode="numeric" value={value.tenorDays ?? ""} hint="Usance LC, DA, open account."
          onChange={(e) => onChange({ ...value, tenorDays: intOrNull(e.target.value) })} inputClassName="t-code" />
        <Input label="Credit limit" optional inputMode="decimal" value={value.creditLimitMinor ? fromMinor(value.creditLimitMinor) : ""}
          hint="DA and open account, buyer side." onChange={(e) => onChange({ ...value, creditLimitMinor: toMinor(e.target.value) })} inputClassName="t-code" />
        <Input label="Credit insurance policy" optional value={value.creditInsuranceRef ?? ""} maxLength={100}
          onChange={(e) => onChange({ ...value, creditInsuranceRef: e.target.value || null })} />
      </div>
    </fieldset>
  );
}

/**
 * A deal's LOIs and contracts as the desk works them (CX-107, A-081): issue
 * both LOIs, then both contracts once the LOIs are signed (refused, naming
 * the term, unless they mirror), countersign for Corridor One X, void.
 */
export function DeskDocumentsPanel({ dealCode }: { dealCode: string }) {
  const toast = useToast();
  const [items, setItems] = useState<DeskDocument[] | null>(null);
  const [sales, setSales] = useState<ContractTerms>(BLANK);
  const [purchase, setPurchase] = useState<ContractTerms>(BLANK);
  const [review, setReview] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [role, setRole] = useState("Authorised signatory");
  const [authority, setAuthority] = useState(false);
  const [voiding, setVoiding] = useState<DeskDocument | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await adminApi.dealDocuments(dealCode));
    } catch {
      setItems(null);
    }
  }, [dealCode]);

  useEffect(() => {
    void load();
  }, [load]);

  if (items === null) return null;
  const run = async (fn: () => Promise<unknown>, done: string) => {
    setBusy(true);
    try {
      await fn();
      toast(done);
      await load();
      return true;
    } catch (e) {
      toast(errorMessage(e, "Couldn’t do that."), "frozen");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const live = items.filter((d) => d.status !== "void");
  const lois = live.filter((d) => d.kind === "loi");
  const contracts = live.filter((d) => d.kind === "contract");
  const loisSigned = lois.length === 2 && lois.every((d) => d.status === "signed");

  return (
    <section aria-labelledby="docs-h" className="relief rounded-[26px] p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="docs-h" className="t-title3 text-fg">
          LOIs and contracts
        </h2>
        {!lois.length ? (
          <Button size="sm" variant="secondary" loading={busy} onClick={() => void run(() => adminApi.issueLois(dealCode), "Both LOIs sent")}>
            Issue LOIs
          </Button>
        ) : null}
      </div>
      {!live.length ? (
        <p className="t-sub mt-2 text-fg-3">Issued from the agreed term sheet once a lawyer has approved the templates.</p>
      ) : null}

      <ul className="mt-4 space-y-3">
        {live.map((d) => {
          const party = d.signatures.find((s) => s.signerType === "party");
          return (
            <li key={d.id} className="well rounded-[18px] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="t-body text-fg">
                  {KIND[d.kind]} · {d.side} · {money(d.valueMinor, d.currency)}
                </p>
                <Chip tone={STATUS[d.status].tone} size="sm" noIcon>
                  {STATUS[d.status].label}
                </Chip>
              </div>
              <p className="t-sub t-code mt-1 text-fg-3">
                {d.template} · term sheet v{d.termSheetVersion} · {d.contentSha256.slice(0, 12)}
                {party ? ` · party signed ${fmtAgo(party.signedAt)} (${party.signerRole})` : ` · sign by ${formatDay(d.expiresAt)}`}
              </p>
              <details className="mt-2">
                <summary className="t-sub cursor-pointer text-fg-3">Read the text</summary>
                <pre className="t-sub mt-2 max-h-80 overflow-auto whitespace-pre-wrap font-mono text-fg">{d.body}</pre>
              </details>
              <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                {d.status !== "effective" ? (
                  <Button size="sm" variant="danger" disabled={busy} onClick={() => setVoiding(d)}>
                    Void…
                  </Button>
                ) : null}
                {d.status === "party_signed" ? (
                  authority && role.trim().length >= 2 ? (
                    <HoldButton
                      size="sm"
                      tone="commit"
                      icon="pen"
                      onCommit={() =>
                        void run(
                          () => adminApi.countersign(d.id, { contentSha256: d.contentSha256, signerRole: role.trim(), authorityConfirmed: true }),
                          "Countersigned for Corridor One X",
                        )
                      }
                    >
                      Countersign
                    </HoldButton>
                  ) : (
                    <span className="t-sub text-fg-3">Confirm your authority below to countersign.</span>
                  )
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>

      {live.some((d) => d.status === "party_signed") ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Input label="Your role" value={role} maxLength={100} onChange={(e) => setRole(e.target.value)} />
          <Checkbox checked={authority} onChange={setAuthority} label="I may sign for Corridor One X" description="Desk managers only." />
        </div>
      ) : null}

      {loisSigned && !contracts.length ? (
        drafting ? (
          <div className="mt-5 space-y-3">
            <div className="grid gap-3 lg:grid-cols-2">
              <TermsForm title="Sales contract (buyer)" value={sales} onChange={setSales} />
              <TermsForm title="Purchase contract (seller)" value={purchase} onChange={setPurchase} />
            </div>
            <Textarea
              label="Legal review"
              optional
              rows={2}
              maxLength={500}
              value={review}
              onChange={(e) => setReview(e.target.value)}
              hint="Who reviewed the contracts. Needed above the legal-review value."
            />
            <p className="t-sub text-fg-3">
              The seller’s penalties must recover at least what the buyer’s would cost, as money, not percentage.
            </p>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="quiet" onClick={() => setDrafting(false)}>
                Cancel
              </Button>
              <Button
                size="sm"
                loading={busy}
                onClick={async () => {
                  const ok = await run(
                    () => adminApi.issueContracts(dealCode, { sales, purchase, legalReviewNote: review.trim() || null }),
                    "Both contracts sent",
                  );
                  if (ok) setDrafting(false);
                }}
              >
                Check and send contracts
              </Button>
            </div>
          </div>
        ) : (
          <div className="mt-4 flex justify-end">
            <Button size="sm" variant="secondary" onClick={() => setDrafting(true)}>
              Draft the contracts
            </Button>
          </div>
        )
      ) : null}

      <RejectSheet
        open={voiding !== null}
        onClose={() => setVoiding(null)}
        title={`Void this ${voiding ? KIND[voiding.kind] : "document"}`}
        description="It can no longer be signed. Issue a new one afterwards."
        quickReasons={["The terms need to change.", "Issued in error."]}
        submitLabel="Void"
        onSubmit={async (reason) => {
          if (!voiding) return;
          await adminApi.voidDocument(voiding.id, reason);
          toast("Voided");
          await load();
        }}
      />
    </section>
  );
}

/**
 * Template versions waiting for a lawyer (CX-108). A super admin records who
 * approved each one; until then nothing built on it can be sent.
 */
export function TemplateApprovals() {
  const toast = useToast();
  const [items, setItems] = useState<ContractTemplate[] | null>(null);
  const [approving, setApproving] = useState<ContractTemplate | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await adminApi.contractTemplates());
    } catch {
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const drafts = items?.filter((t) => t.status === "draft") ?? [];
  if (!drafts.length) return null;

  return (
    <section aria-labelledby="tpl-h" className="relief rounded-[26px] p-5">
      <h2 id="tpl-h" className="t-title3 text-fg">
        Templates waiting for a lawyer · {drafts.length}
      </h2>
      <p className="t-sub mt-1 text-fg-3">No LOI or contract is sent until its template is approved.</p>
      <ul className="mt-4 space-y-3">
        {drafts.map((t) => (
          <li key={t.id} className="well rounded-[18px] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="t-code text-fg">
                {t.code} v{t.version}
              </p>
              <Button size="sm" variant="secondary" onClick={() => setApproving(t)}>
                Record approval…
              </Button>
            </div>
            <details className="mt-2">
              <summary className="t-sub cursor-pointer text-fg-3">Read the template</summary>
              <pre className="t-sub mt-2 max-h-80 overflow-auto whitespace-pre-wrap font-mono text-fg">{t.body}</pre>
            </details>
          </li>
        ))}
      </ul>
      <RejectSheet
        open={approving !== null}
        onClose={() => setApproving(null)}
        title={`Approve ${approving?.code ?? ""} v${approving?.version ?? ""}`}
        description="Name the lawyer, their firm and where their written approval is kept. Super admins only."
        submitLabel="Record approval"
        onSubmit={async (note) => {
          if (!approving) return;
          await adminApi.approveTemplate(approving.id, note);
          toast("Approval recorded");
          await load();
        }}
      />
    </section>
  );
}
