"use client";

import { useCallback, useEffect, useState } from "react";
import {
  adminApi,
  errorMessage,
  type DeskBankAccount,
  type DeskMilestone,
  type StatementLine,
  type StatementMap,
} from "@/lib/adminApi";
import { money } from "@/lib/trade";
import { formatDay } from "@/lib/verification";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { LaneHeader } from "@/components/admin/tower";
import { RejectSheet } from "@/components/admin/RejectSheet";

/**
 * Finance (M5 · S10, CX-020, CX-112, A-083). Money moves at the AD bank;
 * here finance verifies the accounts it may move between, imports the
 * bank's CSV statement, and clears what the rules couldn't match by hand,
 * under the same rules. Businesses appear as company codes.
 */
export default function FinancePage() {
  return (
    <div>
      <LaneHeader
        eyebrow="Finance"
        title="Bank and receipts"
        subtitle="Verify bank accounts, import the bank's statement, and match the payments the rules couldn't."
      />
      <div className="mt-6 space-y-6">
        <AccountsToVerify />
        <ImportStatement />
        <UnmatchedPayments />
      </div>
    </div>
  );
}

function AccountsToVerify() {
  const toast = useToast();
  const [items, setItems] = useState<DeskBankAccount[] | null>(null);
  const [acting, setActing] = useState<{ account: DeskBankAccount; action: "verify" | "reject" | "reveal" } | null>(null);
  const [revealed, setRevealed] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      setItems(await adminApi.pendingBankAccounts());
    } catch {
      setItems([]);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section aria-labelledby="acc-h" className="relief rounded-[26px] p-5">
      <h2 id="acc-h" className="t-title3 text-fg">
        Bank accounts to verify · {items?.length ?? 0}
      </h2>
      {items && !items.length ? <p className="t-sub mt-2 text-fg-3">None waiting.</p> : null}
      <ul className="mt-4 space-y-3">
        {items?.map((a) => (
          <li key={a.id} className="well rounded-[18px] p-4">
            <p className="t-body text-fg">
              <span className="t-code">{a.companyCode ?? "No code"}</span> · {a.bankName} ·{" "}
              <span className="t-code">{revealed[a.id] ?? a.accountMasked}</span> · {a.currency}
            </p>
            <p className="t-sub t-code mt-1 text-fg-3">
              {a.routingCode} · {a.country} · added {formatDay(a.createdAt)}
            </p>
            <div className="mt-3 flex flex-wrap justify-end gap-2">
              <Button size="sm" variant="quiet" onClick={() => setActing({ account: a, action: "reveal" })}>
                Show number…
              </Button>
              <Button size="sm" variant="danger" onClick={() => setActing({ account: a, action: "reject" })}>
                Reject…
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setActing({ account: a, action: "verify" })}>
                Verify…
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <RejectSheet
        open={acting !== null}
        onClose={() => setActing(null)}
        title={acting?.action === "verify" ? "Verify this account" : acting?.action === "reject" ? "Reject this account" : "Show the full number"}
        description={
          acting?.action === "verify"
            ? "Say how it was checked: a penny drop reference, a bank letter. Payouts to it wait out the cooling-off period."
            : acting?.action === "reject"
              ? "The business reads this reason."
              : "Why you need the full number. This is recorded. Finance managers only."
        }
        quickReasons={acting?.action === "verify" ? ["Penny drop matched the holder name."] : []}
        submitLabel={acting?.action === "verify" ? "Verify" : acting?.action === "reject" ? "Reject" : "Show"}
        onSubmit={async (note) => {
          if (!acting) return;
          const { account, action } = acting;
          try {
            if (action === "reveal") {
              const r = await adminApi.revealBankAccount(account.id, note);
              setRevealed((x) => ({ ...x, [account.id]: `${r.accountNumber} · ${r.holderName}` }));
              return;
            }
            await (action === "verify" ? adminApi.verifyBankAccount(account.id, note) : adminApi.rejectBankAccount(account.id, note));
            toast(action === "verify" ? "Account verified" : "Account rejected");
            await load();
          } catch (e) {
            toast(errorMessage(e, "Couldn’t do that."), "frozen");
          }
        }}
      />
    </section>
  );
}

const MAP_FIELDS = [
  ["date", "Date column"],
  ["amount", "Credit amount column"],
  ["reference", "Narration / reference column"],
  ["payer_account", "Remitter account column"],
  ["currency", "Currency column (optional)"],
] as const;

function ImportStatement() {
  const toast = useToast();
  const [maps, setMaps] = useState<StatementMap[] | null>(null);
  const [mapId, setMapId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [newMap, setNewMap] = useState<null | { name: string; dateFormat: string; defaultCurrency: string; columns: Record<string, string> }>(null);

  const load = useCallback(async () => {
    try {
      const m = await adminApi.statementMaps();
      setMaps(m);
      setMapId((id) => id || m[0]?.id || "");
    } catch {
      setMaps(null);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  if (maps === null) return null;
  return (
    <section aria-labelledby="imp-h" className="relief rounded-[26px] p-5">
      <h2 id="imp-h" className="t-title3 text-fg">
        Import a bank statement
      </h2>
      <p className="t-sub mt-1 text-fg-3">
        The bank’s CSV export. Credits from a buyer’s verified account that name the deal code and equal a payment due are matched;
        everything else waits below. The same file is never imported twice.
      </p>
      {maps.length ? (
        <div className="mt-4 grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <Select label="Bank format" value={mapId} options={maps.map((m) => ({ value: m.id, label: m.name }))} onChange={(e) => setMapId(e.target.value)} />
          <Input label="CSV file" type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <Button
            loading={busy}
            disabled={!file || !mapId}
            onClick={async () => {
              if (!file) return;
              setBusy(true);
              try {
                const r = await adminApi.importStatement(mapId, file);
                toast(`${r.linesNew} new credit(s), ${r.linesMatched} matched, ${r.debitsSkipped} debit(s) skipped`, "verified");
              } catch (e) {
                toast(errorMessage(e, "Couldn’t import it."), "frozen");
              } finally {
                setBusy(false);
              }
            }}
          >
            Import
          </Button>
        </div>
      ) : (
        <p className="t-sub mt-3 text-fg-3">Describe your bank’s CSV first.</p>
      )}
      {newMap ? (
        <div className="well mt-4 grid gap-3 rounded-[18px] p-4 sm:grid-cols-2">
          <Input label="Name" value={newMap.name} onChange={(e) => setNewMap({ ...newMap, name: e.target.value })} />
          <Input label="Date format" value={newMap.dateFormat} hint="e.g. %d/%m/%Y" onChange={(e) => setNewMap({ ...newMap, dateFormat: e.target.value })} inputClassName="t-code" />
          {MAP_FIELDS.map(([key, label]) => (
            <Input key={key} label={label} value={newMap.columns[key] ?? ""} hint="The header exactly as in the file."
              onChange={(e) => setNewMap({ ...newMap, columns: { ...newMap.columns, [key]: e.target.value } })} />
          ))}
          <Select label="Default currency" value={newMap.defaultCurrency} options={["INR", "AED", "USD"]}
            onChange={(e) => setNewMap({ ...newMap, defaultCurrency: e.target.value })} />
          <div className="flex items-end justify-end gap-2 sm:col-span-2">
            <Button variant="quiet" onClick={() => setNewMap(null)}>Cancel</Button>
            <Button
              onClick={async () => {
                try {
                  const columns = Object.fromEntries(Object.entries(newMap.columns).filter(([, v]) => v.trim()));
                  await adminApi.createStatementMap({ ...newMap, columns });
                  toast("Bank format saved");
                  setNewMap(null);
                  await load();
                } catch (e) {
                  toast(errorMessage(e, "Couldn’t save it."), "frozen");
                }
              }}
            >
              Save format
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex justify-end">
          <Button size="sm" variant="quiet" onClick={() => setNewMap({ name: "", dateFormat: "%d/%m/%Y", defaultCurrency: "INR", columns: {} })}>
            Add a bank format
          </Button>
        </div>
      )}
    </section>
  );
}

function UnmatchedPayments() {
  const toast = useToast();
  const [items, setItems] = useState<StatementLine[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [milestones, setMilestones] = useState<DeskMilestone[] | null>(null);
  const [aside, setAside] = useState<StatementLine | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await adminApi.unmatchedLines());
    } catch {
      setItems(null);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  if (items === null) return null;
  return (
    <section aria-labelledby="un-h" className="relief rounded-[26px] p-5">
      <h2 id="un-h" className="t-title3 text-fg">
        Payments to match · {items.length}
      </h2>
      {!items.length ? <EmptyState icon="check" title="Nothing waiting">Every credit is matched or set aside.</EmptyState> : null}
      <ul className="mt-4 space-y-3">
        {items.map((line) => (
          <li key={line.id} className="well rounded-[18px] p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="t-body text-fg">
                <span className="t-code">{money(line.amountMinor, line.currency)}</span> · {line.reference || "no narration"}
              </p>
              <span className="t-sub text-fg-3">
                {formatDay(line.bookedOn)} · from ••••{line.payerAccountLast4 ?? "????"}
              </span>
            </div>
            {open === line.id ? (
              <div className="mt-3 space-y-3">
                <div className="flex flex-wrap items-end gap-2">
                  <Input label="Deal code" value={code} placeholder="DL-12345678" onChange={(e) => setCode(e.target.value)} inputClassName="t-code" />
                  <Button size="sm" variant="secondary" onClick={async () => {
                    try {
                      setMilestones((await adminApi.dealMilestones(code.trim())).filter((m) => m.leg === "buyer" && m.status === "open"));
                    } catch (e) {
                      toast(errorMessage(e, "No deal with that code."), "frozen");
                    }
                  }}>
                    Find payments due
                  </Button>
                </div>
                {milestones?.map((m) => (
                  <div key={m.id} className="flex flex-wrap items-center justify-between gap-2">
                    <span className="t-sub text-fg-2">
                      {m.kind.replace("_", " ")} · <span className="t-code">{money(m.amountMinor, m.currency)}</span>
                    </span>
                    <Button size="sm" onClick={async () => {
                      try {
                        await adminApi.matchLine(line.id, m.id, `Matched by hand to ${code.trim()} ${m.kind}.`);
                        toast("Matched; the payment is cleared", "verified");
                        setOpen(null);
                        await load();
                      } catch (e) {
                        toast(errorMessage(e, "Couldn’t match it."), "frozen");
                      }
                    }}>
                      Match to this
                    </Button>
                  </div>
                ))}
                {milestones && !milestones.length ? <p className="t-sub text-fg-3">No open payments due on that deal.</p> : null}
              </div>
            ) : (
              <div className="mt-3 flex flex-wrap justify-end gap-2">
                <Button size="sm" variant="quiet" onClick={() => setAside(line)}>Set aside…</Button>
                <Button size="sm" variant="secondary" onClick={() => { setOpen(line.id); setCode(""); setMilestones(null); }}>
                  Match by hand
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <RejectSheet
        open={aside !== null}
        onClose={() => setAside(null)}
        title="Set this credit aside"
        description="For a credit that isn't a trade receipt: a refund, interest, a return. Say what it is."
        quickReasons={["Interest credited by the bank.", "Not a buyer account; returned to the sender."]}
        submitLabel="Set aside"
        onSubmit={async (note) => {
          if (!aside) return;
          await adminApi.setAsideLine(aside.id, note);
          toast("Set aside");
          await load();
        }}
      />
    </section>
  );
}
