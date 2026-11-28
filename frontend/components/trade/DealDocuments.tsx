"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { trade, type DealDocument } from "@/lib/trade";
import { formatDay } from "@/lib/verification";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { Checkbox, HoldButton } from "@/components/ui/Controls";
import { Input } from "@/components/ui/Field";
import { Card, SolidPanel } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";

const TITLE = { loi: "Letter of intent", contract: "Contract" } as const;
const STATUS: Record<DealDocument["status"], { label: string; tone: ChipTone }> = {
  issued: { label: "Your move", tone: "move" },
  party_signed: { label: "Waiting for Corridor One X", tone: "move" },
  signed: { label: "Signed", tone: "verified" },
  effective: { label: "In effect", tone: "verified" },
  void: { label: "Void", tone: "neutral" },
};

function Paper({ doc }: { doc: DealDocument }) {
  return (
    <pre className="well t-sub mt-3 max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-[18px] p-4 font-mono text-fg">
      {doc.body}
    </pre>
  );
}

function SignForm({ dealCode, doc, onSigned }: { dealCode: string; doc: DealDocument; onSigned: () => Promise<void> }) {
  const toast = useToast();
  const [role, setRole] = useState("");
  const [authority, setAuthority] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sign = async () => {
    setError(null);
    try {
      await trade.signDocument(dealCode, doc.id, { contentSha256: doc.contentSha256, signerRole: role.trim(), authorityConfirmed: authority });
      toast("Signed. Corridor One X countersigns next.", "verified");
      await onSigned();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn’t sign it. Try again.");
      await onSigned();
    }
  };

  return (
    <div className="mt-4 space-y-3">
      <Input label="Your role" value={role} maxLength={100} placeholder="e.g. Director" onChange={(e) => setRole(e.target.value)} />
      <Checkbox
        checked={authority}
        onChange={setAuthority}
        label="I am authorised to sign for my company"
        description="Signing binds your company to this document as written above."
      />
      {error ? <p role="alert" className="t-sub text-danger">{error}</p> : null}
      <div className="flex justify-end">
        {role.trim().length >= 2 && authority ? (
          <HoldButton tone="commit" icon="pen" onCommit={() => void sign()}>
            Hold to sign
          </HoldButton>
        ) : (
          <p className="t-sub text-fg-3">Enter your role and confirm your authority to sign.</p>
        )}
      </div>
    </div>
  );
}

/**
 * This side's letters of intent and contracts (CX-107, A-081). Each party
 * reads and signs only its own document; the signature carries the hash
 * of the exact text shown. The other side's document is never shown here.
 */
export function DealDocuments({ dealCode, canWrite }: { dealCode: string; canWrite: boolean }) {
  const [items, setItems] = useState<DealDocument[] | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await trade.listDocuments(dealCode));
    } catch {
      setItems([]);
    }
  }, [dealCode]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!items?.length) return null;
  const live = items.filter((d) => d.status !== "void");
  const past = items.filter((d) => d.status === "void");

  return (
    <Card as="section" aria-labelledby="docs-title" className="rounded-[26px] p-5 sm:p-6">
      <h2 id="docs-title" className="t-title3 text-fg">
        Documents to sign
      </h2>
      <p className="t-sub mt-1 text-fg-3">Between your company and Corridor One X only. Read it in full before you sign.</p>

      <ul className="mt-4 space-y-5">
        {live.map((doc) => {
          const s = STATUS[doc.status];
          const head = (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="t-callout font-medium text-fg">{TITLE[doc.kind]}</p>
              <Chip tone={s.tone} size="sm" noIcon>
                {s.label}
              </Chip>
            </div>
          );
          const facts = (
            <p className="t-sub mt-1 text-fg-3">
              {doc.status === "effective"
                ? `In effect since ${formatDay(doc.effectiveAt)}`
                : doc.youSignedAt
                  ? `You signed on ${formatDay(doc.youSignedAt)}`
                  : `Sign by ${formatDay(doc.expiresAt)}`}
              {" · "}
              <span className="t-code">Reference {doc.contentSha256.slice(0, 12)}</span>
            </p>
          );
          return (
            <li key={doc.id}>
              {doc.status === "effective" || doc.status === "signed" ? (
                <SolidPanel className="p-5">
                  {head}
                  {facts}
                  <Paper doc={doc} />
                </SolidPanel>
              ) : (
                <div>
                  {head}
                  {facts}
                  <Paper doc={doc} />
                  {doc.status === "issued" && canWrite ? <SignForm dealCode={dealCode} doc={doc} onSigned={load} /> : null}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {past.length ? (
        <details className="mt-4">
          <summary className="t-sub cursor-pointer text-fg-3">Void documents · {past.length}</summary>
          <ul className="mt-2 space-y-1">
            {past.map((d) => (
              <li key={d.id} className="t-sub flex justify-between gap-2 text-fg-2">
                <span>
                  {TITLE[d.kind]} of {formatDay(d.issuedAt)}
                </span>
                <span>{d.voidReason}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Card>
  );
}
