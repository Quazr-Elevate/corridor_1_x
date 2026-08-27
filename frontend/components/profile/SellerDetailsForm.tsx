"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Check, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { api } from "@/lib/api";
import { useMe } from "@/lib/useMe";

export function SellerDetailsForm() {
  const { me, refetch } = useMe();
  const businessDone = !!me?.completion.business;

  const [udyam, setUdyam] = useState("");
  const [aadhaar, setAadhaar] = useState("");
  const [tan, setTan] = useState("");

  // Pre-fill from server
  useEffect(() => {
    if (!me?.seller) return;
    setUdyam(me.seller.udyam ?? "");
    setAadhaar(me.seller.aadhaar ?? "");
    setTan(me.seller.tan ?? "");
  }, [me?.seller]);

  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!savedAt) return;
    const t = window.setTimeout(() => setSavedAt(null), 3000);
    return () => window.clearTimeout(t);
  }, [savedAt]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!businessDone) {
      setError("Fill Business details first before adding Seller details.");
      return;
    }
    setSaving(true);
    try {
      await api.saveProfileSeller({
        udyam: udyam.trim() || null,
        aadhaar: aadhaar.trim() || null,
        tan: tan.trim().toUpperCase() || null,
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
      {!businessDone ? (
        <div className="flex items-start gap-3 rounded-lg border border-line bg-ink-elevated/60 p-4">
          <ShieldAlert aria-hidden className="mt-0.5 h-4 w-4 text-accent" />
          <div>
            <p className="text-sm text-paper">Business details required first</p>
            <p className="mt-1 text-xs text-paper-muted">
              Add your PAN and company under Business details, then come back here.
            </p>
          </div>
        </div>
      ) : null}

      <TextField
        label="Udyam registration number"
        placeholder="e.g. UDYAM-XX-00-0000000"
        value={udyam}
        onChange={(e) => setUdyam(e.target.value)}
        optional
      />
      <TextField
        label="Aadhaar number"
        placeholder="12-digit Aadhaar"
        inputMode="numeric"
        maxLength={12}
        value={aadhaar}
        onChange={(e) => setAadhaar(e.target.value.replace(/\D/g, "").slice(0, 12))}
        optional
        hint="Handled with care — for prod, we'll move Aadhaar to a vaulted store."
      />
      <TextField
        label="TAN"
        placeholder="10 characters"
        autoCapitalize="characters"
        maxLength={10}
        value={tan}
        onChange={(e) => setTan(e.target.value.toUpperCase())}
        optional
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
        <Button type="submit" loading={saving} disabled={!businessDone}>
          Save seller details <ArrowRight aria-hidden className="h-4 w-4" />
        </Button>
      </div>
    </form>
  );
}
