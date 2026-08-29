"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { AmbientBackground } from "@/components/brand/AmbientBackground";
import { BrandHeader } from "@/components/brand/BrandHeader";
import { Button } from "@/components/ui/Button";
import { FieldWithAction } from "@/components/ui/FieldWithAction";
import { OtpModal } from "@/components/ui/OtpModal";
import { TextField } from "@/components/ui/TextField";
import { api, storeUserId } from "@/lib/api";
import { personNameField, phoneRegex } from "@/lib/validation";

type Mode = "login" | "signup";

interface Props {
  mode: Mode;
  onAuthed: (userId: string, isNew: boolean) => void;
}

const CONSENT_VERSION = "T-2026-08-29";

/**
 * Unified phone-first auth shell. One page, two fields for signup:
 *
 *   [full name] [mobile] [✓ consent] → Verify mobile
 *      ↓ OTP modal → verify
 *   Login path (existing mobile): cookie set → dashboard
 *   Signup path (new mobile):     name + consent submitted with the verify
 *                                 (bridge cookie carries the phone through)
 *
 * Email is intentionally NOT collected here. Users add + verify it from
 * the profile page — an unverified email is worse than no email.
 */
export function AuthShell({ mode, onAuthed }: Props) {
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Backend uses a specific detail string for the mode/existence mismatch;
  // we sniff it to render a "sign in / sign up instead" cross-link chip.
  const [crossLink, setCrossLink] = useState<null | "toLogin" | "toSignup">(null);
  const [sending, setSending] = useState(false);
  const [otp, setOtp] = useState<{
    open: boolean;
    otpId?: string;
    destination?: string;
    devHint?: string;
  }>({ open: false });

  const phoneValid = phoneRegex.test(phone.trim());
  // Name + consent are only required on the signup route — /login uses the
  // same shell but a returning user only needs to punch in the mobile.
  const nameNeeded = mode === "signup";
  const nameValid = !nameNeeded || personNameField.safeParse(fullName).success;
  const consentOk = !nameNeeded || consent;
  const canSend = phoneValid && nameValid && consentOk;

  const sendOtp = async () => {
    setError(null);
    setCrossLink(null);
    if (!phoneValid) return setError("Enter a valid 10-digit Indian mobile number");
    if (nameNeeded && !nameValid) {
      const msg = personNameField.safeParse(fullName).success
        ? ""
        : "Enter your full name (letters only)";
      return setError(msg);
    }
    if (nameNeeded && !consentOk) {
      return setError("Please accept the Terms and Privacy Policy to continue");
    }
    setSending(true);
    try {
      const res = await api.sendOtp({
        channel: "phone",
        value: phone.trim(),
        purpose: "phone",
        mode,
      });
      setOtp({
        open: true,
        otpId: res.otpId,
        destination: res.destination,
        devHint: res.devHint,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not send code";
      setError(msg);
      // Backend uses the phrase "sign in instead" for signup-mode duplicates
      // and "sign up first" for login-mode misses. Cheap sniff so the UI can
      // offer a one-tap jump to the correct page.
      if (mode === "signup" && /sign in instead/i.test(msg)) setCrossLink("toLogin");
      else if (mode === "login" && /sign up first/i.test(msg)) setCrossLink("toSignup");
    } finally {
      setSending(false);
    }
  };

  const handleVerify = async (code: string) => {
    if (!otp.otpId) return { ok: false, error: "Session expired" };
    try {
      const res = await api.verifyOtp({
        otpId: otp.otpId,
        code,
        mobile: phone.trim(),
        mode,
      });
      if (!res.ok) return { ok: false, error: res.error };

      // Login path — backend already set the session cookie.
      if (!res.isNew && res.userId) {
        setOtp({ open: false });
        storeUserId(res.userId);
        onAuthed(res.userId, false);
        return { ok: true };
      }

      // Signup path — the verified-phone bridge cookie is set. Finalize
      // account creation with name + consent. We do this from inside the
      // verify handler so it feels like a single step to the user.
      try {
        const signed = await api.signup({
          fullName: fullName.trim(),
          consent: true,
          consentVersion: CONSENT_VERSION,
        });
        setOtp({ open: false });
        storeUserId(signed.userId);
        onAuthed(signed.userId, signed.isNew);
        return { ok: true };
      } catch (err) {
        return {
          ok: false,
          error: err instanceof Error ? err.message : "Could not create account",
        };
      }
    } catch (err) {
      return {
        ok: false,
        error: err instanceof Error ? err.message : "Verification failed",
      };
    }
  };

  const handleResend = async () => {
    if (!phone) return;
    await api.sendOtp({ channel: "phone", value: phone.trim(), purpose: "phone" });
  };

  const copy =
    mode === "signup"
      ? {
          eyebrow: "Create account",
          title: { lead: "One number.", highlight: "One account." },
          subtitle:
            "Just your name and mobile. We'll verify it and drop you straight into your dashboard — email and business details come later.",
        }
      : {
          eyebrow: "Sign in",
          title: { lead: "Welcome back.", highlight: "Pick up where you left off." },
          subtitle:
            "Enter the mobile you signed up with. We'll send a one-time code — no password.",
        };

  return (
    <main className="relative min-h-dvh overflow-hidden bg-ink text-paper safe-x">
      <AmbientBackground />

      <div
        className="relative mx-auto w-full max-w-[440px] px-4 pb-14 pt-6 sm:max-w-md sm:px-5 sm:pt-10 lg:max-w-[560px]"
        style={{
          paddingTop: "max(env(safe-area-inset-top), 24px)",
          paddingBottom: "max(env(safe-area-inset-bottom), 56px)",
        }}
      >
        <BrandHeader
          eyebrow={copy.eyebrow}
          title={copy.title}
          subtitle={copy.subtitle}
        />

        <section className="mt-8 surface p-4 sm:p-5 enter" data-delay="5">
          {nameNeeded && (
            <TextField
              label="Full name"
              placeholder="Your name"
              autoComplete="name"
              value={fullName}
              onChange={(e) => {
                setFullName(e.target.value);
                if (error) setError(null);
              }}
              className="mb-4"
            />
          )}

          <FieldWithAction
            label="Mobile number"
            placeholder="Enter mobile number"
            inputMode="numeric"
            maxLength={10}
            autoComplete="tel-national"
            value={phone}
            onChange={(e) => {
              const clean = e.target.value.replace(/\D/g, "").slice(0, 10);
              setPhone(clean);
              if (error) setError(null);
            }}
            action={
              <Button
                variant="inline"
                onClick={sendOtp}
                loading={sending}
                disabled={!canSend}
              >
                Send OTP
              </Button>
            }
          />

          {nameNeeded && (
            <label className="mt-4 flex items-start gap-2 text-xs text-paper-muted">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5 h-3.5 w-3.5 rounded border-line bg-ink accent-accent"
              />
              <span>
                I accept Cor1x&apos;s{" "}
                <a
                  href="/terms"
                  target="_blank"
                  className="text-accent underline-offset-4 hover:underline"
                >
                  Terms
                </a>{" "}
                and{" "}
                <a
                  href="/privacy"
                  target="_blank"
                  className="text-accent underline-offset-4 hover:underline"
                >
                  Privacy Policy
                </a>
                .
              </span>
            </label>
          )}

          {error && (
            <div className="mt-3 space-y-1.5">
              <p className="text-sm font-medium text-danger">{error}</p>
              {crossLink === "toLogin" && (
                <a
                  href="/login"
                  className="inline-flex items-center gap-1 text-xs text-accent underline-offset-4 hover:underline"
                >
                  Go to sign in <ArrowRight aria-hidden className="h-3 w-3" />
                </a>
              )}
              {crossLink === "toSignup" && (
                <a
                  href="/signup"
                  className="inline-flex items-center gap-1 text-xs text-accent underline-offset-4 hover:underline"
                >
                  Create an account <ArrowRight aria-hidden className="h-3 w-3" />
                </a>
              )}
            </div>
          )}

          {nameNeeded && (
            <p className="mt-4 rounded-lg border border-dashed border-line px-3 py-2.5 text-xs text-paper-muted">
              <span aria-hidden className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-accent align-middle" />
              You&apos;ll add email, GSTIN, and bank details from your profile — each verified in place.
            </p>
          )}
        </section>

        <p
          className="mt-6 flex items-center justify-center gap-1.5 text-[10px] uppercase tracking-widest text-paper-muted enter"
          data-delay="9"
        >
          <span aria-hidden className="h-1 w-1 rounded-full bg-accent" />
          No unverified hands in between
        </p>

        <p className="mt-4 text-center text-xs text-paper-muted">
          {mode === "signup" ? (
            <>
              Already have an account?{" "}
              <a href="/login" className="text-accent underline-offset-4 hover:underline">
                Sign in <ArrowRight aria-hidden className="inline h-3 w-3" />
              </a>
            </>
          ) : (
            <>
              New to Cor1x?{" "}
              <a href="/signup" className="text-accent underline-offset-4 hover:underline">
                Create an account
              </a>
            </>
          )}
        </p>
      </div>

      <OtpModal
        open={otp.open}
        destination={otp.destination ?? ""}
        devHint={otp.devHint}
        onClose={() => setOtp({ open: false })}
        onVerify={handleVerify}
        onResend={handleResend}
      />
    </main>
  );
}
