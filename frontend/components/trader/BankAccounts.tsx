"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type BankAccount } from "@/lib/api";
import { formatDay } from "@/lib/verification";
import { Button } from "@/components/ui/Button";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { Segmented } from "@/components/ui/Controls";
import { Input } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";

const STATUS: Record<BankAccount["status"], { label: string; tone: ChipTone }> = {
  pending: { label: "Being verified", tone: "move" },
  verified: { label: "Verified", tone: "verified" },
  rejected: { label: "Not accepted", tone: "frozen" },
  retired: { label: "Replaced", tone: "neutral" },
};

/**
 * The company's bank accounts (CX-020): one per currency. Numbers are
 * shown masked; a new account for a currency replaces the old one and is
 * verified again before any payment uses it.
 */
export function BankAccounts() {
  const toast = useToast();
  const [items, setItems] = useState<BankAccount[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ currency: "INR", country: "IN", bankName: "", routingCode: "", accountNumber: "", holderName: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await api.listBankAccounts());
    } catch {
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.addBankAccount(form);
      toast("Account added. Corridor One X will verify it.", "verified");
      setAdding(false);
      setForm((f) => ({ ...f, bankName: "", routingCode: "", accountNumber: "", holderName: "" }));
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn’t add the account.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {items?.length ? (
        <ul className="space-y-2">
          {items.map((a) => (
            <li key={a.id} className="well flex flex-wrap items-center justify-between gap-2 rounded-[18px] p-4">
              <div>
                <p className="t-callout font-medium text-fg">
                  {a.bankName} · <span className="t-code">{a.accountMasked}</span> · {a.currency}
                </p>
                <p className="t-sub text-fg-3">
                  <span className="t-code">{a.routingCode}</span> · added {formatDay(a.createdAt)}
                  {a.rejectedReason ? ` · ${a.rejectedReason}` : ""}
                </p>
              </div>
              <Chip tone={STATUS[a.status].tone} size="sm" noIcon>
                {STATUS[a.status].label}
              </Chip>
            </li>
          ))}
        </ul>
      ) : items ? (
        <p className="t-sub text-fg-3">No bank account yet. Add one before your first payment.</p>
      ) : null}

      {adding ? (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Segmented label="Currency" value={form.currency} onChange={(v) => set("currency", v)}
              options={[{ value: "INR", label: "INR" }, { value: "AED", label: "AED" }, { value: "USD", label: "USD" }]} />
            <Segmented label="Bank country" value={form.country} onChange={(v) => set("country", v)}
              options={[{ value: "IN", label: "India" }, { value: "AE", label: "UAE" }]} />
            <Input label="Bank" value={form.bankName} maxLength={100} onChange={(e) => set("bankName", e.target.value)} />
            <Input label={form.country === "IN" ? "IFSC" : "SWIFT / BIC"} value={form.routingCode} maxLength={20}
              placeholder={form.country === "IN" ? "HDFC0001234" : "EBILAEAD"} onChange={(e) => set("routingCode", e.target.value)} inputClassName="t-code" />
            <Input label="Account number or IBAN" value={form.accountNumber} maxLength={40} autoComplete="off"
              onChange={(e) => set("accountNumber", e.target.value)} inputClassName="t-code" />
            <Input label="Account holder" value={form.holderName} maxLength={150} hint="Exactly as the bank has it."
              onChange={(e) => set("holderName", e.target.value)} />
          </div>
          {error ? <p role="alert" className="t-sub text-danger">{error}</p> : null}
          <p className="t-sub text-fg-3">Adding an account for a currency replaces the one you have, and it is verified again.</p>
          <div className="flex justify-end gap-2">
            <Button variant="quiet" onClick={() => setAdding(false)}>Cancel</Button>
            <Button loading={busy} onClick={() => void save()}>Add account</Button>
          </div>
        </div>
      ) : (
        <Button variant="secondary" onClick={() => setAdding(true)}>Add a bank account</Button>
      )}
    </div>
  );
}
