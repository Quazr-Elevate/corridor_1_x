"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { FieldWithAction } from "@/components/ui/FieldWithAction";
import { TextField } from "@/components/ui/TextField";
import { api } from "@/lib/api";
import { useDirtyFlag } from "@/lib/useUnsavedGuard";
import { useFocusField } from "@/lib/useFocusField";
import { useMe } from "@/lib/useMe";
import { gstinRegex, panRegex } from "@/lib/validation";

/**
 * GSTIN + PAN are verified in-place — one click hits Masters India and,
 * on success, stamps the value + verified_at on the server atomically.
 * Only after that will /profile/business accept a company_name change.
 */
export function BusinessDetailsForm() {
  const { me, refetch } = useMe();
  useFocusField();

  const [gstin, setGstin] = useState("");
  const [gstinVerified, setGstinVerified] = useState(false);
  const [gstinSending, setGstinSending] = useState(false);
  const [gstinError, setGstinError] = useState<string | null>(null);

  const [pan, setPan] = useState("");
  const [panVerified, setPanVerified] = useState(false);
  const [panSending, setPanSending] = useState(false);
  const [panError, setPanError] = useState<string | null>(null);

  const [companyName, setCompanyName] = useState("");

  useEffect(() => {
    if (!me?.business) return;
    setGstin(me.business.gstin ?? "");
    setGstinVerified(!!me.business.gstinVerifiedAt);
    setPan(me.business.pan ?? "");
    setPanVerified(!!me.business.panVerifiedAt);
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
    return companyName.trim() !== (b.companyName ?? "").trim();
  }, [me, companyName]);
  useDirtyFlag(dirty);

  const gstinValid = gstinRegex.test(gstin.trim().toUpperCase());
  const panValid = panRegex.test(pan.trim().toUpperCase());

  const verifyGstin = async () => {
    setGstinError(null);
    if (!gstinValid) return setGstinError("Enter a valid 15-character GSTIN");
    setGstinSending(true);
    try {
      const res = await api.verifyGstin(gstin.trim().toUpperCase());
      setGstinVerified(true);
      // GSTIN verify also stamps PAN + fills company_name (derived).
      setPanVerified(true);
      if (res.lookup?.pan) setPan(res.lookup.pan);
      if (res.lookup?.legalName && !companyName.trim()) {
        setCompanyName(res.lookup.legalName);
      }
      await refetch();
    } catch (err) {
      setGstinError(err instanceof Error ? err.message : "Could not verify GSTIN");
    } finally {
      setGstinSending(false);
    }
  };

  const verifyPan = async () => {
    setPanError(null);
    if (!panValid) return setPanError("Enter a valid 10-character PAN");
    setPanSending(true);
    try {
      const res = await api.verifyPan(pan.trim().toUpperCase());
      setPanVerified(true);
      if (res.name && !companyName.trim()) setCompanyName(res.name);
      await refetch();
    } catch (err) {
      setPanError(err instanceof Error ? err.message : "Could not verify PAN");
    } finally {
      setPanSending(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!panVerified) {
      setError("Verify PAN before saving company details");
      return;
    }
    if (!companyName.trim()) {
      setError("Company name is required");
      return;
    }
    setSaving(true);
    try {
      // Send back the verified values so the server can confirm no change.
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
      <FieldWithAction
        label={gstinVerified ? "GSTIN · verified" : "GSTIN"}
        placeholder="Optional — 15 characters"
        hint={gstinVerified ? undefined : "Skip if you don't have one; PAN is enough."}
        autoCapitalize="characters"
        autoComplete="off"
        spellCheck={false}
        maxLength={15}
        value={gstin}
        onChange={(e) => {
          setGstin(e.target.value.toUpperCase());
          if (gstinVerified) setGstinVerified(false);
          if (gstinError) setGstinError(null);
        }}
        readOnly={gstinVerified}
        error={gstinError ?? undefined}
        action={
          gstinVerified ? (
            <Button variant="inline" type="button" onClick={() => setGstinVerified(false)}>
              Change
            </Button>
          ) : (
            <Button
              variant="inline"
              type="button"
              onClick={verifyGstin}
              loading={gstinSending}
              disabled={!gstinValid}
            >
              Verify
            </Button>
          )
        }
      />
      <FieldWithAction
        label={panVerified ? "PAN · verified" : "PAN"}
        placeholder="ABCDE1234F"
        hint={panVerified ? undefined : "10 characters — required"}
        autoCapitalize="characters"
        autoComplete="off"
        spellCheck={false}
        maxLength={10}
        value={pan}
        onChange={(e) => {
          setPan(e.target.value.toUpperCase());
          if (panVerified) setPanVerified(false);
          if (panError) setPanError(null);
        }}
        readOnly={panVerified}
        error={panError ?? undefined}
        action={
          panVerified ? (
            <Button variant="inline" type="button" onClick={() => setPanVerified(false)}>
              Change
            </Button>
          ) : (
            <Button
              variant="inline"
              type="button"
              onClick={verifyPan}
              loading={panSending}
              disabled={!panValid}
            >
              Verify
            </Button>
          )
        }
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
        <Button type="submit" loading={saving} disabled={!panVerified}>
          Save business details <ArrowRight aria-hidden className="h-4 w-4" />
        </Button>
      </div>
    </form>
  );
}
