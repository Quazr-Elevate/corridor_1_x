"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { AmbientBackground } from "@/components/brand/AmbientBackground";
import { BrandHeader } from "@/components/brand/BrandHeader";
import { Button } from "@/components/ui/Button";
import { FieldWithAction } from "@/components/ui/FieldWithAction";
import { OtpModal } from "@/components/ui/OtpModal";
import { TextField } from "@/components/ui/TextField";
import { api, storeUserId } from "@/lib/api";
import { emailField, personNameField, phoneRegex } from "@/lib/validation";

type Mode = "login" | "signup";

interface Props {
  mode: Mode;
  onAuthed: (userId: string, isNew: boolean) => void;
}

const CONSENT_VERSION = "T-2026-08-29";

/**
 * Unified phone-first auth shell. One page, progressive reveal:
 *
 *   [phone]                                            (always visible)
 *      ↓ Send OTP
 *   OtpModal → verify
 *      ↓
 *   Login path (existing mobile):
 *     - Backend set cor1x_session cookie
 *     - onAuthed(userId, isNew=false) → parent redirects to dashboard
 *
 *   Signup path (new mobile):
 *     - Backend set cor1x_verified_phone bridge cookie
 *     - INLINE reveal: full name + email + consent + Create account
 *     - Submit → /auth/signup → onAuthed(userId, isNew=true)
 *
 * Used by both /login (mode=login) and /signup (mode=signup) — the mode
 * only tweaks copy + which flow surprises the user. Either landing page
 * gracefully handles either outcome (existing user on /signup → welcome
 * back; new user on /login → sign-up form appears with a friendly note).
 */
export function AuthShell({ mode, onAuthed }: Props) {
  const [phone, setPhone] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [otp, setOtp] = useState<{
    open: boolean;
    otpId?: string;
    destination?: string;
    devHint?: string;
  }>({ open: false });

  // Only set after successful OTP verify → "true" reveals signup fields
  const [needsSignup, setNeedsSignup] = useState(false);
  const [verifiedMobile, setVerifiedMobile] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [signupError, setSignupError] = useState<string | null>(null);
  const [signingUp, setSigningUp] = useState(false);

  const phoneValid = phoneRegex.test(phone.trim());

  const sendOtp = async () => {
    setPhoneError(null);
    if (!phoneValid) {
      setPhoneError("Enter a valid 10-digit Indian mobile number");
      return;
    }
    setSending(true);
    try {
      const res = await api.sendOtp({
        channel: "phone",
        value: phone.trim(),
        purpose: mode === "login" ? "phone" : "phone",
      });
      setOtp({
        open: true,
        otpId: res.otpId,
        destination: res.destination,
        devHint: res.devHint,
      });
    } catch (err) {
      setPhoneError(err instanceof Error ? err.message : "Could not send code");
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
      });
      if (!res.ok) return { ok: false, error: res.error };

      setOtp({ open: false });
      setVerifiedMobile(phone.trim());

      if (res.isNew) {
        // No account yet — reveal signup fields on the same page.
        setNeedsSignup(true);
      } else if (res.userId) {
        // Login: cookie set. Also cache userId for legacy X-User-Id header path.
        storeUserId(res.userId);
        onAuthed(res.userId, false);
      }
      return { ok: true };
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

  const submitSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setSignupError(null);

    // Validate on the client first for a nicer message than the 400.
    const nameCheck = personNameField.safeParse(fullName);
    if (!nameCheck.success) {
      setSignupError(nameCheck.error.issues[0].message);
      return;
    }
    const emailCheck = emailField.safeParse(email);
    if (!emailCheck.success) {
      setSignupError(emailCheck.error.issues[0].message);
      return;
    }
    if (!consent) {
      setSignupError("Please accept the Terms and Privacy Policy to continue");
      return;
    }

    setSigningUp(true);
    try {
      const res = await api.signup({
        fullName: nameCheck.data,
        email: emailCheck.data,
        consent: true,
        consentVersion: CONSENT_VERSION,
      });
      storeUserId(res.userId);
      onAuthed(res.userId, res.isNew);
    } catch (err) {
      setSignupError(
        err instanceof Error ? err.message : "Could not create account",
      );
    } finally {
      setSigningUp(false);
    }
  };

  const copy =
    mode === "signup"
      ? {
          eyebrow: "Create account",
          title: { lead: "One number.", highlight: "One account." },
          subtitle:
            "Sign up with your mobile. We'll verify it, ask for the essentials, and unlock your dashboard.",
        }
      : {
          eyebrow: "Sign in",
          title: { lead: "Welcome back.", highlight: "Pick up where you left off." },
          subtitle:
            "Enter the mobile you signed up with. We'll send a one-time code — no password.",
        };

  return (
    <main className="relative min-h-screen overflow-hidden bg-ink text-paper">
      <AmbientBackground />

      <div className="relative mx-auto w-full max-w-[440px] px-4 pb-14 pt-6 sm:max-w-md sm:px-5 sm:pt-10 lg:max-w-[560px]">
        <BrandHeader
          eyebrow={copy.eyebrow}
          title={copy.title}
          subtitle={copy.subtitle}
        />

        <motion.section
          className="mt-8 surface p-4 sm:p-5 enter"
          data-delay="5"
        >
          {/* Phone step — always visible */}
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
              if (phoneError) setPhoneError(null);
            }}
            readOnly={needsSignup || Boolean(verifiedMobile && !needsSignup)}
            error={phoneError ?? undefined}
            action={
              <Button
                variant="inline"
                onClick={sendOtp}
                loading={sending}
                disabled={!phoneValid || needsSignup || Boolean(verifiedMobile)}
                data-verified={Boolean(verifiedMobile) || undefined}
              >
                {verifiedMobile ? "Verified" : "Send OTP"}
              </Button>
            }
          />

          {/* Signup step — revealed only if the mobile is new */}
          <AnimatePresence>
            {needsSignup && (
              <motion.form
                onSubmit={submitSignup}
                className="mt-6 space-y-4"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              >
                <p className="rounded-lg border border-dashed border-line px-3 py-2.5 text-xs text-paper-muted">
                  <span aria-hidden className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-accent align-middle" />
                  New here — just two quick fields and you&apos;re in.
                </p>

                <TextField
                  label="Full name"
                  placeholder="Your name"
                  autoComplete="name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
                <TextField
                  label="Email"
                  placeholder="you@example.com"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />

                <label className="flex items-start gap-2 text-xs text-paper-muted">
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

                {signupError && (
                  <p className="text-sm font-medium text-danger">{signupError}</p>
                )}

                <Button
                  type="submit"
                  className="w-full"
                  loading={signingUp}
                  disabled={!fullName || !email || !consent}
                >
                  Create account <ArrowRight aria-hidden className="h-4 w-4" />
                </Button>
              </motion.form>
            )}
          </AnimatePresence>
        </motion.section>

        <p className="mt-6 flex items-center justify-center gap-1.5 text-[10px] uppercase tracking-widest text-paper-muted enter" data-delay="9">
          <span aria-hidden className="h-1 w-1 rounded-full bg-accent" />
          Encrypted · DPDP-compliant · never shared
        </p>

        <p className="mt-4 text-center text-xs text-paper-muted">
          {mode === "signup" ? (
            <>
              Already have an account?{" "}
              <a href="/login" className="text-accent underline-offset-4 hover:underline">
                Sign in
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
