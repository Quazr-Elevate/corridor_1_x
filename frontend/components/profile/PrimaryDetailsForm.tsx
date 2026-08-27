"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { FieldWithAction } from "@/components/ui/FieldWithAction";
import { OtpModal } from "@/components/ui/OtpModal";
import { TextField } from "@/components/ui/TextField";
import { api } from "@/lib/api";
import { INDIA_STATES, normalizeState } from "@/lib/indiaStates";
import { useDirtyFlag } from "@/lib/useUnsavedGuard";
import { useFocusField } from "@/lib/useFocusField";
import { useMe } from "@/lib/useMe";
import { personNameRegex, phoneRegex } from "@/lib/validation";

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type OtpTarget = "email" | "altMobile" | "altEmail" | "businessEmail";

export function PrimaryDetailsForm() {
  const { me, refetch } = useMe();
  useFocusField();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [pincode, setPincode] = useState("");
  // Additional
  const [altMobile, setAltMobile] = useState("");
  const [altEmail, setAltEmail] = useState("");
  const [businessEmail, setBusinessEmail] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [googleBusinessUrl, setGoogleBusinessUrl] = useState("");
  const [facebookUrl, setFacebookUrl] = useState("");

  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [pincodeErr, setPincodeErr] = useState<string | null>(null);
  const [pincodeLoading, setPincodeLoading] = useState(false);

  const dirty = useMemo(() => {
    const p = me?.primary;
    if (!p) return false;
    const norm = (s: string | null | undefined) => (s ?? "").trim();
    return (
      fullName.trim() !== norm(p.fullName) ||
      email.trim() !== norm(p.email) ||
      addressLine.trim() !== norm(p.addressLine) ||
      city.trim() !== norm(p.city) ||
      state !== norm(p.state) ||
      pincode !== norm(p.pincode) ||
      altMobile !== norm(p.altMobile) ||
      altEmail.trim() !== norm(p.altEmail) ||
      businessEmail.trim() !== norm(p.businessEmail) ||
      websiteUrl.trim() !== norm(p.websiteUrl) ||
      googleBusinessUrl.trim() !== norm(p.googleBusinessUrl) ||
      facebookUrl.trim() !== norm(p.facebookUrl)
    );
  }, [
    me,
    fullName,
    email,
    addressLine,
    city,
    state,
    pincode,
    altMobile,
    altEmail,
    businessEmail,
    websiteUrl,
    googleBusinessUrl,
    facebookUrl,
  ]);
  useDirtyFlag(dirty);

  // Resolve pincode → city (and state if not yet set). Silent on failure —
  // the field just stays empty and the user types manually.
  const resolvePincode = async (code: string) => {
    setPincodeLoading(true);
    try {
      const loc = await api.lookupPincode(code);
      if (loc.city) setCity(loc.city);
      if (loc.state && !state) {
        const canonical = normalizeState(loc.state);
        if (canonical) setState(canonical);
      }
    } catch (err) {
      setPincodeErr(err instanceof Error ? err.message : "Pincode lookup failed");
    } finally {
      setPincodeLoading(false);
    }
  };

  // Verification state per verifiable field
  const [emailVerified, setEmailVerified] = useState(false);
  const [emailSending, setEmailSending] = useState(false);
  const [emailErr, setEmailErr] = useState<string | null>(null);

  const [altVerified, setAltVerified] = useState(false);
  const [altSending, setAltSending] = useState(false);
  const [altErr, setAltErr] = useState<string | null>(null);

  const [altEmailVerified, setAltEmailVerified] = useState(false);
  const [altEmailSending, setAltEmailSending] = useState(false);
  const [altEmailErr, setAltEmailErr] = useState<string | null>(null);

  const [bizEmailVerified, setBizEmailVerified] = useState(false);
  const [bizEmailSending, setBizEmailSending] = useState(false);
  const [bizEmailErr, setBizEmailErr] = useState<string | null>(null);

  // One shared modal, keyed by which field triggered it
  const [otp, setOtp] = useState<{
    open: boolean;
    target?: OtpTarget;
    otpId?: string;
    destination?: string;
    devHint?: string;
  }>({ open: false });

  const emailValid = emailRegex.test(email.trim().toLowerCase());
  const altMobileValid = phoneRegex.test(altMobile.trim());
  const altEmailValid = emailRegex.test(altEmail.trim().toLowerCase());
  const bizEmailValid = emailRegex.test(businessEmail.trim().toLowerCase());
  const bizMatchesPrimary =
    bizEmailValid &&
    emailVerified &&
    businessEmail.trim().toLowerCase() === email.trim().toLowerCase();

  useEffect(() => {
    if (!savedAt) return;
    const t = window.setTimeout(() => setSavedAt(null), 3000);
    return () => window.clearTimeout(t);
  }, [savedAt]);

  // Pre-fill from server on load — treat anything the server already has as previously verified
  useEffect(() => {
    if (!me?.primary) return;
    setFullName(me.primary.fullName ?? "");
    setEmail(me.primary.email ?? "");
    setEmailVerified(!!me.primary.email);
    setAddressLine(me.primary.addressLine ?? "");
    setCity(me.primary.city ?? "");
    setState(me.primary.state ?? "");
    setPincode(me.primary.pincode ?? "");
    setAltMobile(me.primary.altMobile ?? "");
    setAltVerified(!!me.primary.altMobile);
    setAltEmail(me.primary.altEmail ?? "");
    setAltEmailVerified(!!me.primary.altEmail);
    setBusinessEmail(me.primary.businessEmail ?? "");
    setBizEmailVerified(!!me.primary.businessEmail);
    setWebsiteUrl(me.primary.websiteUrl ?? "");
    setGoogleBusinessUrl(me.primary.googleBusinessUrl ?? "");
    setFacebookUrl(me.primary.facebookUrl ?? "");
  }, [me?.primary]);

  // ── Send OTP helpers, one per field ─────────────────────────────────────

  const sendEmailOtp = async () => {
    setEmailErr(null);
    if (!emailValid) {
      setEmailErr("Enter a valid email address");
      return;
    }
    setEmailSending(true);
    try {
      const res = await api.sendOtp({
        channel: "email",
        value: email.trim().toLowerCase(),
        purpose: "email",
      });
      setOtp({
        open: true,
        target: "email",
        otpId: res.otpId,
        destination: res.destination,
        devHint: res.devHint,
      });
    } catch (err) {
      setEmailErr(err instanceof Error ? err.message : "Could not send code");
    } finally {
      setEmailSending(false);
    }
  };

  const sendAltMobileOtp = async () => {
    setAltErr(null);
    if (!altMobileValid) {
      setAltErr("Enter a valid 10-digit mobile number");
      return;
    }
    if (me?.mobile && altMobile.trim() === me.mobile) {
      setAltErr("Alternative must differ from your primary mobile");
      return;
    }
    setAltSending(true);
    try {
      const res = await api.sendOtp({
        channel: "phone",
        value: altMobile.trim(),
        purpose: "phone",
      });
      setOtp({
        open: true,
        target: "altMobile",
        otpId: res.otpId,
        destination: res.destination,
        devHint: res.devHint,
      });
    } catch (err) {
      setAltErr(err instanceof Error ? err.message : "Could not send code");
    } finally {
      setAltSending(false);
    }
  };

  // Auto-verify business email if it matches the (verified) primary email.
  useEffect(() => {
    if (bizMatchesPrimary && !bizEmailVerified) {
      setBizEmailVerified(true);
      setBizEmailErr(null);
    }
  }, [bizMatchesPrimary, bizEmailVerified]);

  const sendBizEmailOtp = async () => {
    setBizEmailErr(null);
    if (!bizEmailValid) {
      setBizEmailErr("Enter a valid business email");
      return;
    }
    setBizEmailSending(true);
    try {
      const res = await api.sendOtp({
        channel: "email",
        value: businessEmail.trim().toLowerCase(),
        purpose: "email",
      });
      setOtp({
        open: true,
        target: "businessEmail",
        otpId: res.otpId,
        destination: res.destination,
        devHint: res.devHint,
      });
    } catch (err) {
      setBizEmailErr(err instanceof Error ? err.message : "Could not send code");
    } finally {
      setBizEmailSending(false);
    }
  };

  const sendAltEmailOtp = async () => {
    setAltEmailErr(null);
    if (!altEmailValid) {
      setAltEmailErr("Enter a valid email address");
      return;
    }
    if (altEmail.trim().toLowerCase() === email.trim().toLowerCase()) {
      setAltEmailErr("Alternative email must differ from your primary email");
      return;
    }
    setAltEmailSending(true);
    try {
      const res = await api.sendOtp({
        channel: "email",
        value: altEmail.trim().toLowerCase(),
        purpose: "email",
      });
      setOtp({
        open: true,
        target: "altEmail",
        otpId: res.otpId,
        destination: res.destination,
        devHint: res.devHint,
      });
    } catch (err) {
      setAltEmailErr(err instanceof Error ? err.message : "Could not send code");
    } finally {
      setAltEmailSending(false);
    }
  };

  const handleVerify = async (code: string) => {
    if (!otp.otpId || !otp.target) return { ok: false, error: "Session expired" };
    const target = otp.target;
    const isEmail = target === "email" || target === "altEmail" || target === "businessEmail";
    const value =
      target === "email"
        ? email.trim().toLowerCase()
        : target === "altEmail"
        ? altEmail.trim().toLowerCase()
        : target === "businessEmail"
        ? businessEmail.trim().toLowerCase()
        : altMobile.trim();
    try {
      const res = await api.verifyOtp({
        otpId: otp.otpId,
        code,
        channel: isEmail ? "email" : "phone",
        ...(isEmail ? { email: value } : { mobile: value }),
      });
      if (res.ok) {
        if (target === "email") setEmailVerified(true);
        if (target === "altMobile") setAltVerified(true);
        if (target === "altEmail") setAltEmailVerified(true);
        if (target === "businessEmail") setBizEmailVerified(true);
        setOtp({ open: false });
      }
      return res;
    } catch (err) {
      return {
        ok: false,
        error: err instanceof Error ? err.message : "Verification failed",
      };
    }
  };

  const handleResend = async () => {
    if (!otp.target) return;
    const target = otp.target;
    const isEmail = target === "email" || target === "altEmail" || target === "businessEmail";
    const value =
      target === "email"
        ? email.trim().toLowerCase()
        : target === "altEmail"
        ? altEmail.trim().toLowerCase()
        : target === "businessEmail"
        ? businessEmail.trim().toLowerCase()
        : altMobile.trim();
    await api.sendOtp({
      channel: isEmail ? "email" : "phone",
      value,
      purpose: isEmail ? "email" : "phone",
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNameError(null);
    setEmailErr(null);
    setAltErr(null);
    setAltEmailErr(null);
    setBizEmailErr(null);

    const name = fullName.trim();
    if (!personNameRegex.test(name)) {
      setNameError("Name should not contain numbers");
      return;
    }
    // Email is optional for save. Only block save if the user typed an email
    // but hasn't verified it — otherwise unverified addresses would sneak in.
    if (email.trim() && !emailValid) {
      setEmailErr("Enter a valid email address, or clear the field before saving");
      return;
    }
    if (email.trim() && !emailVerified) {
      setEmailErr("Verify this email with OTP, or clear the field before saving");
      return;
    }
    if (altMobile.trim() && !altVerified) {
      setAltErr("Verify this number with OTP, or clear the field before saving");
      return;
    }
    if (altEmail.trim() && !altEmailVerified) {
      setAltEmailErr("Verify this email with OTP, or clear the field before saving");
      return;
    }
    if (businessEmail.trim() && !bizEmailVerified) {
      setBizEmailErr("Verify this email with OTP, or clear the field before saving");
      return;
    }

    setSaving(true);
    try {
      await api.saveProfilePrimary({
        fullName: name,
        email: email.trim() ? email.trim().toLowerCase() : null,
        addressLine: addressLine.trim() || null,
        city: city.trim() || null,
        state: state.trim() || null,
        pincode: pincode.trim() || null,
        altMobile: altMobile.trim() || null,
        altEmail: altEmail.trim().toLowerCase() || null,
        businessEmail: businessEmail.trim().toLowerCase() || null,
        websiteUrl: websiteUrl.trim() || null,
        googleBusinessUrl: googleBusinessUrl.trim() || null,
        facebookUrl: facebookUrl.trim() || null,
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
    <form onSubmit={handleSubmit} className="space-y-8" noValidate>
      {/* Contact */}
      <section className="space-y-4">
        <SectionLabel>Contact details</SectionLabel>
        <TextField
          id="f-full-name"
          label="Full name"
          placeholder="Enter your full name"
          value={fullName}
          onChange={(e) => {
            const next = e.target.value;
            setFullName(next);
            // Live check: flag digits only. Length + other-char checks run on
            // submit so a single letter mid-typing doesn't flash an error.
            if (/\d/.test(next)) {
              setNameError("Name should not contain numbers");
            } else {
              setNameError(null);
            }
          }}
          error={nameError ?? undefined}
          autoComplete="name"
          required
        />
        <TextField
          label="Mobile number"
          value={me?.mobile ? `+91 ${me.mobile.slice(0, 5)} ${me.mobile.slice(5)}` : ""}
          readOnly
          autofill
        />
        <FieldWithAction
          id="f-email-address"
          label={emailVerified ? "Email address · verified" : "Email address"}
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (emailVerified) setEmailVerified(false);
            if (emailErr) setEmailErr(null);
          }}
          readOnly={emailVerified}
          error={emailErr ?? undefined}
          autoComplete="email"
          action={
            emailVerified ? (
              <Button variant="inline" type="button" onClick={() => setEmailVerified(false)}>
                Change
              </Button>
            ) : (
              <Button
                variant="inline"
                type="button"
                onClick={sendEmailOtp}
                loading={emailSending}
                disabled={!emailValid}
              >
                Send OTP
              </Button>
            )
          }
        />
        <TextField
          label="Address"
          placeholder="Street, area, landmark"
          value={addressLine}
          onChange={(e) => setAddressLine(e.target.value)}
        />
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label htmlFor="f-state" className="field-label">
              <span>State</span>
            </label>
            <select
              id="f-state"
              className="field"
              value={state}
              onChange={(e) => setState(e.target.value)}
            >
              <option value="">Select state</option>
              {INDIA_STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <TextField
            label="Pincode"
            inputMode="numeric"
            maxLength={6}
            placeholder="6-digit pincode"
            value={pincode}
            onChange={(e) => {
              const clean = e.target.value.replace(/\D/g, "").slice(0, 6);
              setPincode(clean);
              if (pincodeErr) setPincodeErr(null);
              if (clean.length === 6) void resolvePincode(clean);
            }}
            error={pincodeErr ?? undefined}
          />
          <TextField
            label="City"
            placeholder={pincodeLoading ? "Looking up…" : "City"}
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
        </div>
      </section>

      {/* Additional (sub-card) */}
      <section className="space-y-4 rounded-lg border border-dashed border-line p-4">
        <SectionLabel>Additional details · optional</SectionLabel>

        <FieldWithAction
          label={altVerified ? "Alternative mobile · verified" : "Alternative mobile"}
          placeholder="10-digit number"
          inputMode="numeric"
          maxLength={10}
          autoComplete="tel-national"
          value={altMobile}
          onChange={(e) => {
            const clean = e.target.value.replace(/\D/g, "").slice(0, 10);
            setAltMobile(clean);
            if (altVerified) setAltVerified(false);
            if (altErr) setAltErr(null);
          }}
          readOnly={altVerified}
          error={altErr ?? undefined}
          action={
            altVerified ? (
              <Button variant="inline" type="button" onClick={() => setAltVerified(false)}>
                Change
              </Button>
            ) : (
              <Button
                variant="inline"
                type="button"
                onClick={sendAltMobileOtp}
                loading={altSending}
                disabled={!altMobileValid}
              >
                Send OTP
              </Button>
            )
          }
        />

        <FieldWithAction
          label={altEmailVerified ? "Alternative email · verified" : "Alternative email"}
          type="email"
          placeholder="you+alt@example.com"
          value={altEmail}
          onChange={(e) => {
            setAltEmail(e.target.value);
            if (altEmailVerified) setAltEmailVerified(false);
            if (altEmailErr) setAltEmailErr(null);
          }}
          readOnly={altEmailVerified}
          error={altEmailErr ?? undefined}
          action={
            altEmailVerified ? (
              <Button variant="inline" type="button" onClick={() => setAltEmailVerified(false)}>
                Change
              </Button>
            ) : (
              <Button
                variant="inline"
                type="button"
                onClick={sendAltEmailOtp}
                loading={altEmailSending}
                disabled={!altEmailValid}
              >
                Send OTP
              </Button>
            )
          }
        />

        <FieldWithAction
          label={
            bizMatchesPrimary
              ? "Business email · auto-verified (same as primary)"
              : bizEmailVerified
              ? "Business email · verified"
              : "Business email"
          }
          type="email"
          placeholder="orders@company.com"
          hint={
            bizMatchesPrimary
              ? undefined
              : "Shared inbox for buyer enquiries. Type your primary email to skip OTP."
          }
          value={businessEmail}
          onChange={(e) => {
            setBusinessEmail(e.target.value);
            // Always reset — auto-verify effect re-sets if it matches primary
            setBizEmailVerified(false);
            if (bizEmailErr) setBizEmailErr(null);
          }}
          readOnly={bizEmailVerified && !bizMatchesPrimary}
          error={bizEmailErr ?? undefined}
          action={
            bizMatchesPrimary ? (
              <span className="inline-flex h-full items-center px-2 text-[10px] uppercase tracking-widest text-accent">
                Auto
              </span>
            ) : bizEmailVerified ? (
              <Button variant="inline" type="button" onClick={() => setBizEmailVerified(false)}>
                Change
              </Button>
            ) : (
              <Button
                variant="inline"
                type="button"
                onClick={sendBizEmailOtp}
                loading={bizEmailSending}
                disabled={!bizEmailValid}
              >
                Send OTP
              </Button>
            )
          }
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Website URL"
            placeholder="https://…"
            value={websiteUrl}
            onChange={(e) => setWebsiteUrl(e.target.value)}
          />
          <TextField
            label="Google Business URL"
            placeholder="https://g.co/…"
            value={googleBusinessUrl}
            onChange={(e) => setGoogleBusinessUrl(e.target.value)}
          />
          <TextField
            label="Facebook URL"
            placeholder="https://facebook.com/…"
            value={facebookUrl}
            onChange={(e) => setFacebookUrl(e.target.value)}
            className="sm:col-span-2"
          />
        </div>
      </section>

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
          Save primary details <ArrowRight aria-hidden className="h-4 w-4" />
        </Button>
      </div>

      <OtpModal
        open={otp.open}
        destination={otp.destination ?? ""}
        devHint={otp.devHint}
        onClose={() => setOtp({ open: false })}
        onVerify={handleVerify}
        onResend={handleResend}
      />
    </form>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] uppercase tracking-widest text-paper-muted">
      {children}
    </p>
  );
}
