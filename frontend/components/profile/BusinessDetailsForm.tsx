"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { api } from "@/lib/api";
import { useDirtyFlag } from "@/lib/useUnsavedGuard";
import { useFocusField } from "@/lib/useFocusField";
import { useMe } from "@/lib/useMe";
import { gstinRegex, panRegex } from "@/lib/validation";

export function BusinessDetailsForm() {
  const { me, refetch } = useMe();
  useFocusField();

  const [gstin, setGstin] = useState("");
  const [pan, setPan] = useState("");
  const [companyName, setCompanyName] = useState("");

  // Pre-fill from server
  useEffect(() => {
    if (!me?.business) return;
    setGstin(me.business.gstin ?? "");
    setPan(me.business.pan ?? "");
    setCompanyName(me.business.companyName ?? "");
  }, [me?.business]);

  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!savedAt) return;
    const t = window.setTimeout(() => setSavedAt(null), 3000);
    return () => window.clearTimeout(t);
  }, [savedAt]);

  const dirty = useMemo(() => {
    const b = me?.business;
    if (!b) return false;
    const norm = (s: string | null | undefined) => (s ?? "").trim();
    return (
      gstin.trim() !== norm(b.gstin) ||
      pan.trim() !== norm(b.pan) ||
      companyName.trim() !== norm(b.companyName)
    );
  }, [me, gstin, pan, companyName]);
  useDirtyFlag(dirty);

  const [gstinError, setGstinError] = useState<string | null>(null);
  const [panError, setPanError] = useState<string | null>(null);

  const validate = () => {
    let ok = true;
    if (gstin && !gstinRegex.test(gstin.trim().toUpperCase())) {
      setGstinError("Enter a valid 15-character GSTIN");
      ok = false;
    }
    if (!panRegex.test(pan.trim().toUpperCase())) {
      setPanError("Enter a valid 10-character PAN");
      ok = false;
    }
    return ok;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setGstinError(null);
    setPanError(null);
    if (!validate()) return;
    if (!companyName.trim()) {
      setError("Company name is required");
      return;
    }
    setSaving(true);
    try {
      await api.saveProfileBusiness({
        gstin: gstin.trim() ? gstin.trim().toUpperCase() : null,
        pan: pan.trim().toUpperCase(),
        companyName: companyName.trim(),
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
        label="GSTIN"
        placeholder="Optional — 15 characters"
        hint="Skip if you don't have one; PAN is enough."
        autoCapitalize="characters"
        autoComplete="off"
        spellCheck={false}
        maxLength={15}
        value={gstin}
        onChange={(e) => {
          setGstin(e.target.value.toUpperCase());
          if (gstinError) setGstinError(null);
        }}
        error={gstinError ?? undefined}
      />
      <TextField
        label="PAN"
        placeholder="ABCDE1234F"
        hint="10 characters — required"
        autoCapitalize="characters"
        autoComplete="off"
        spellCheck={false}
        maxLength={10}
        value={pan}
        onChange={(e) => {
          setPan(e.target.value.toUpperCase());
          if (panError) setPanError(null);
        }}
        error={panError ?? undefined}
        required
      />
      <TextField
        label="Company name"
        placeholder="Legal registered name"
        value={companyName}
        onChange={(e) => setCompanyName(e.target.value)}
        autoComplete="organization"
        required
      />

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
          Save business details <ArrowRight aria-hidden className="h-4 w-4" />
        </Button>
      </div>
    </form>
  );
}
