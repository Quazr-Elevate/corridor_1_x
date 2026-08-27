"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { api } from "@/lib/api";
import { useDirtyFlag } from "@/lib/useUnsavedGuard";
import { useFocusField } from "@/lib/useFocusField";
import { useMe } from "@/lib/useMe";
import { personNameRegex } from "@/lib/validation";

const ifscRegex = /^[A-Z]{4}0[A-Z0-9]{6}$/;

export function BankDetailsForm() {
  const { me, refetch } = useMe();
  useFocusField();

  const [accountNumber, setAccountNumber] = useState("");
  const [ifsc, setIfsc] = useState("");
  const [holderName, setHolderName] = useState("");
  const [branchName, setBranchName] = useState("");
  const [bankName, setBankName] = useState("");

  // Pre-fill from server
  useEffect(() => {
    if (!me?.bank) return;
    setAccountNumber(me.bank.accountNumber ?? "");
    setIfsc(me.bank.ifsc ?? "");
    setHolderName(me.bank.holderName ?? "");
    setBranchName(me.bank.branchName ?? "");
    setBankName(me.bank.bankName ?? "");
  }, [me?.bank]);

  const [lookingUp, setLookingUp] = useState(false);
  const [ifscError, setIfscError] = useState<string | null>(null);
  const [holderError, setHolderError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!savedAt) return;
    const t = window.setTimeout(() => setSavedAt(null), 3000);
    return () => window.clearTimeout(t);
  }, [savedAt]);

  const dirty = useMemo(() => {
    const b = me?.bank;
    if (!b) return false;
    const norm = (s: string | null | undefined) => (s ?? "").trim();
    return (
      accountNumber.trim() !== norm(b.accountNumber) ||
      ifsc.trim() !== norm(b.ifsc) ||
      holderName.trim() !== norm(b.holderName) ||
      branchName.trim() !== norm(b.branchName) ||
      bankName.trim() !== norm(b.bankName)
    );
  }, [me, accountNumber, ifsc, holderName, branchName, bankName]);
  useDirtyFlag(dirty);

  const ifscValid = ifscRegex.test(ifsc.trim().toUpperCase());

  const lookupIfsc = async () => {
    setIfscError(null);
    if (!ifscValid) {
      setIfscError("Enter a valid 11-character IFSC (e.g. HDFC0001234)");
      return;
    }
    setLookingUp(true);
    try {
      const res = await api.lookupIfsc(ifsc.trim().toUpperCase());
      setBankName(res.bank);
      setBranchName(res.branch);
    } catch (err) {
      setIfscError(err instanceof Error ? err.message : "IFSC lookup failed");
    } finally {
      setLookingUp(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setHolderError(null);
    if (!accountNumber.trim() || !ifscValid || !holderName.trim()) {
      setError("Account number, IFSC and holder name are required");
      return;
    }
    if (!personNameRegex.test(holderName.trim())) {
      setHolderError("Name should not contain numbers");
      return;
    }
    setSaving(true);
    try {
      await api.saveProfileBank({
        accountNumber: accountNumber.trim(),
        ifsc: ifsc.trim().toUpperCase(),
        holderName: holderName.trim(),
        branchName: branchName.trim() || null,
        bankName: bankName.trim() || null,
      });
      setSavedAt(Date.now());
      await refetch();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      <TextField
        label="Account number"
        placeholder="Bank account number"
        inputMode="numeric"
        value={accountNumber}
        onChange={(e) =>
          setAccountNumber(e.target.value.replace(/\s/g, "").slice(0, 30))
        }
        autoComplete="off"
        required
      />

      <div>
        <label htmlFor="f-ifsc" className="field-label">
          <span>IFSC</span>
          {branchName && bankName ? (
            <span className="text-[10px] uppercase tracking-widest text-accent">
              ✓ Fetched
            </span>
          ) : null}
        </label>
        <div className="field-row" data-invalid={ifscError ? true : undefined}>
          <input
            id="f-ifsc"
            className="field"
            placeholder="HDFC0001234"
            autoCapitalize="characters"
            autoComplete="off"
            spellCheck={false}
            maxLength={11}
            value={ifsc}
            onChange={(e) => {
              setIfsc(e.target.value.toUpperCase());
              if (ifscError) setIfscError(null);
            }}
          />
          <div className="flex items-center pr-1">
            <Button
              variant="inline"
              onClick={lookupIfsc}
              loading={lookingUp}
              disabled={!ifscValid}
              type="button"
            >
              Fetch
            </Button>
          </div>
        </div>
        {ifscError ? (
          <p className="field-error" role="alert">
            {ifscError}
          </p>
        ) : (
          <p className="mt-1.5 text-xs text-paper-muted">
            11 characters — auto-fills bank and branch
          </p>
        )}
      </div>

      <TextField
        id="f-account-holder-name"
        label="Account holder name"
        placeholder="Full name on the account"
        value={holderName}
        onChange={(e) => {
          const next = e.target.value;
          setHolderName(next);
          if (/\d/.test(next)) {
            setHolderError("Name should not contain numbers");
          } else {
            setHolderError(null);
          }
        }}
        error={holderError ?? undefined}
        autoComplete="name"
        required
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Branch name"
          placeholder="Auto-fill after IFSC"
          value={branchName}
          onChange={(e) => setBranchName(e.target.value)}
          autofill
          readOnly
        />
        <TextField
          label="Bank name"
          placeholder="Auto-fill after IFSC"
          value={bankName}
          onChange={(e) => setBankName(e.target.value)}
          autofill
          readOnly
        />
      </div>

      {error ? <p className="text-sm font-medium text-danger">{error}</p> : null}

      <div className="flex items-center justify-between gap-4">
        {savedAt ? (
          <p className="inline-flex items-center gap-1.5 text-xs text-accent">
            <Check className="h-3.5 w-3.5" aria-hidden />
            Saved
          </p>
        ) : (
          <span />
        )}
        <Button type="submit" loading={saving}>
          Save bank details <ArrowRight aria-hidden className="h-4 w-4" />
        </Button>
      </div>
    </form>
  );
}
