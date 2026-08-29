"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { ArrowRight, ChevronLeft, Lock, Scale, ShieldCheck } from "lucide-react";
import { OtpModal } from "@/components/ui/OtpModal";
import { api, storeUserId } from "@/lib/api";
import { personNameField, phoneRegex } from "@/lib/validation";

type Mode = "login" | "signup";

interface Props {
  mode: Mode;
  onAuthed: (userId: string, isNew: boolean) => void;
}

const CONSENT_VERSION = "T-2026-08-29";

/**
 * Auth screens — styled 1:1 after the mobile design canvas (Cor1x Mobile
 * .dc.html): top bar with inset-ring back button + wordmark, eyebrow chip
 * with pulsing dot, 26px display headline with chartreuse highlight,
 * ink-sunken inputs with inset rings, dashed hint boxes, a single
 * full-width CTA with its "what's blocking you" caption underneath, trust
 * rows, and the ENCRYPTED footer strip. Screen fades up on entry
 * (fadeUp 0.45s ease 0.08s — same as the design).
 *
 * Flow logic is unchanged from the iterated build: phone-first, mode-aware
 * duplicate rejection, OTP modal, signup finalized inside the verify
 * handler so it reads as one step.
 */
export function AuthShell({ mode, onAuthed }: Props) {
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [crossLink, setCrossLink] = useState<null | "toLogin" | "toSignup">(null);
  const [sending, setSending] = useState(false);
  const [otp, setOtp] = useState<{
    open: boolean;
    otpId?: string;
    destination?: string;
    devHint?: string;
  }>({ open: false });

  const phoneValid = phoneRegex.test(phone.trim());
  const nameNeeded = mode === "signup";
  const nameValid = !nameNeeded || personNameField.safeParse(fullName).success;
  const consentOk = !nameNeeded || consent;
  const canSend = phoneValid && nameValid && consentOk;

  const sendOtp = async () => {
    setError(null);
    setCrossLink(null);
    if (!phoneValid) return setError("Enter a valid 10-digit Indian mobile number");
    if (nameNeeded && !nameValid) {
      return setError("Enter your full name (letters only)");
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

      if (!res.isNew && res.userId) {
        setOtp({ open: false });
        storeUserId(res.userId);
        onAuthed(res.userId, false);
        return { ok: true };
      }

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
    await api.sendOtp({ channel: "phone", value: phone.trim(), purpose: "phone", mode });
  };

  const copy =
    mode === "signup"
      ? {
          title: "Sign up",
          eyebrow: "CREATE ACCOUNT · VERIFIED ONBOARDING",
          headLead: "One number.",
          headAccent: "One account.",
          subtitle:
            "Just your name and mobile. Email, GSTIN, and bank details come later — each verified in place.",
          ctaCaption: canSend
            ? "We'll text a one-time code to verify"
            : "Fill your name and mobile to continue",
        }
      : {
          title: "Log in",
          eyebrow: "MEMBER · SECURE LOG IN",
          headLead: "Back to",
          headAccent: "the corridor.",
          subtitle: "Log in with the phone number registered to your business.",
          ctaCaption: canSend
            ? "We'll text a one-time code — no password"
            : "Enter your registered mobile to continue",
        };

  return (
    <main
      className="auth-screen-glow relative min-h-dvh overflow-y-auto text-paper safe-x"
      style={{
        animation: "fadeUp 0.45s ease 0.08s both",
        paddingTop: "max(env(safe-area-inset-top), 24px)",
        paddingBottom: "max(env(safe-area-inset-bottom), 24px)",
      }}
    >
      <div className="mx-auto flex min-h-[calc(100dvh-48px)] w-full max-w-[440px] flex-col px-[22px] sm:max-w-md lg:max-w-[480px]">
        {/* ── Top bar: back · title · wordmark ── */}
        <div className="flex items-center gap-3 pt-4">
          <Link
            href="/?intro=0"
            aria-label="Back"
            className="-ml-1.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-[6px] bg-ink-soft text-paper-soft shadow-[inset_0_0_0_1px_#3A3F38] transition-colors hover:text-paper"
          >
            <ChevronLeft aria-hidden className="h-5 w-5" />
          </Link>
          <p className="text-[18px] font-bold tracking-tight text-paper">
            {copy.title}
          </p>
          <Image
            src="/brand/wordmark.png"
            alt="Corridor One X"
            width={1583}
            height={173}
            priority
            className="ml-auto w-[118px] select-none opacity-85"
          />
        </div>

        {/* ── Eyebrow chip ── */}
        <div className="mt-5 inline-flex items-center gap-[7px] self-start rounded-[6px] bg-ink-soft px-3 py-1.5 text-[10px] font-extrabold tracking-[0.14em] text-paper-soft shadow-[inset_0_0_0_1px_#3A3F38]">
          <span
            aria-hidden
            className="h-1.5 w-1.5 rounded-full bg-accent"
            style={{ animation: "glowPulse 1.8s ease infinite" }}
          />
          {copy.eyebrow}
        </div>

        {/* ── Headline + subtitle ── */}
        <h1
          className="mt-3 text-[26px] font-bold leading-[1.2] tracking-[-0.01em] text-paper"
          style={{ textWrap: "pretty" }}
        >
          {copy.headLead} <span className="text-accent">{copy.headAccent}</span>
        </h1>
        <p
          className="mt-2 text-[13px] leading-[1.55] text-paper-muted"
          style={{ textWrap: "pretty" }}
        >
          {copy.subtitle}
        </p>

        {/* ── Form ── */}
        <div className="mt-6 flex flex-col gap-4">
          {nameNeeded && (
            <div>
              <label
                htmlFor="auth-name"
                className="mb-2 block text-[11px] font-bold uppercase tracking-[0.1em] text-paper-muted"
              >
                Full name
              </label>
              <input
                id="auth-name"
                placeholder="Your name"
                autoComplete="name"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  if (error) setError(null);
                }}
                className="h-12 w-full rounded-[6px] bg-ink px-3.5 text-[15px] text-paper shadow-[inset_0_0_0_1px_#3A3F38] outline-none transition-shadow placeholder:text-paper-muted/60 focus:shadow-[inset_0_0_0_1px_rgba(196,216,46,0.5)]"
              />
            </div>
          )}

          <div>
            <label
              htmlFor="auth-phone"
              className="mb-2 block text-[11px] font-bold uppercase tracking-[0.1em] text-paper-muted"
            >
              Phone number
            </label>
            <div className="flex h-12 gap-2">
              <span className="flex items-center rounded-[6px] bg-ink px-[13px] text-[14px] font-bold text-paper-soft shadow-[inset_0_0_0_1px_#3A3F38]">
                +91
              </span>
              <input
                id="auth-phone"
                placeholder="98765 43210"
                inputMode="numeric"
                maxLength={10}
                autoComplete="tel-national"
                value={phone}
                onChange={(e) => {
                  const clean = e.target.value.replace(/\D/g, "").slice(0, 10);
                  setPhone(clean);
                  if (error) setError(null);
                }}
                className="h-12 min-w-0 flex-1 rounded-[6px] bg-ink px-3.5 text-[15px] tracking-wide text-paper shadow-[inset_0_0_0_1px_#3A3F38] outline-none transition-shadow placeholder:text-paper-muted/60 focus:shadow-[inset_0_0_0_1px_rgba(196,216,46,0.5)]"
              />
            </div>
          </div>

          {nameNeeded ? (
            <label className="flex items-start gap-2 text-[11.5px] leading-[1.5] text-paper-muted">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5 h-3.5 w-3.5 rounded border-line bg-ink accent-accent"
              />
              <span>
                I accept Cor1x&apos;s{" "}
                <a href="/terms" target="_blank" className="text-accent underline-offset-4 hover:underline">
                  Terms
                </a>{" "}
                and{" "}
                <a href="/privacy" target="_blank" className="text-accent underline-offset-4 hover:underline">
                  Privacy Policy
                </a>
                .
              </span>
            </label>
          ) : (
            <p className="text-[11.5px] leading-[1.5] text-paper-muted">
              By continuing you agree to Cor1x&apos;s{" "}
              <a href="/terms" target="_blank" className="text-accent underline-offset-4 hover:underline">
                Terms
              </a>{" "}
              and{" "}
              <a href="/privacy" target="_blank" className="text-accent underline-offset-4 hover:underline">
                Privacy Policy
              </a>
              .
            </p>
          )}

          {nameNeeded && (
            <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-line px-[13px] py-[11px] text-[11.5px] leading-[1.5] text-paper-muted">
              <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              You&apos;ll add email, GSTIN, and bank details from your profile —
              each verified in place.
            </div>
          )}

          {/* ── CTA + caption ── */}
          <button
            type="button"
            onClick={sendOtp}
            disabled={!canSend || sending}
            className={
              canSend
                ? "flex h-[52px] items-center justify-center gap-1.5 rounded-[6px] bg-accent text-[15px] font-extrabold text-accent-fg shadow-[0_6px_16px_rgba(0,0,0,0.35)] transition-all duration-150 hover:bg-accent-hover active:scale-[0.985] disabled:opacity-70"
                : "flex h-[52px] items-center justify-center gap-1.5 rounded-[6px] bg-ink-soft text-[15px] font-extrabold text-paper-muted shadow-[inset_0_0_0_1px_#3A3F38]"
            }
          >
            {sending ? "Sending…" : "Send OTP"}
            {canSend && !sending && <ArrowRight aria-hidden className="h-4 w-4" />}
          </button>
          <p className="-mt-1 text-center text-[12px] text-paper-muted">
            {copy.ctaCaption}
          </p>

          {error && (
            <div className="space-y-1.5">
              <p className="text-[13px] font-semibold text-danger">{error}</p>
              {crossLink === "toLogin" && (
                <a href="/login" className="inline-flex items-center gap-1 text-[12px] font-semibold text-accent underline-offset-4 hover:underline">
                  Go to log in <ArrowRight aria-hidden className="h-3 w-3" />
                </a>
              )}
              {crossLink === "toSignup" && (
                <a href="/signup" className="inline-flex items-center gap-1 text-[12px] font-semibold text-accent underline-offset-4 hover:underline">
                  Create an account <ArrowRight aria-hidden className="h-3 w-3" />
                </a>
              )}
            </div>
          )}
        </div>

        {/* ── Trust rows (design: signup screen) ── */}
        {nameNeeded && (
          <div className="mt-8 flex flex-col gap-3">
            <TrustRow
              icon={<ShieldCheck aria-hidden className="h-4 w-4 text-accent" strokeWidth={2} />}
              label="Verified counterparties"
              caption="KYB-cleared before contact"
            />
            <TrustRow
              icon={<Lock aria-hidden className="h-4 w-4 text-accent" strokeWidth={2} />}
              label="Contact stays private"
              caption="Revealed to verified buyers only"
            />
            <TrustRow
              icon={<Scale aria-hidden className="h-4 w-4 text-accent" strokeWidth={2} />}
              label="Circumvention protection"
              caption="Every reveal is audited"
            />
          </div>
        )}

        {/* ── Cross-mode link ── */}
        <p className="mt-6 text-center text-[12px] text-paper-muted">
          {mode === "signup" ? (
            <>
              Already have an account?{" "}
              <a href="/login" className="font-semibold text-accent underline-offset-4 hover:underline">
                Log in
              </a>
            </>
          ) : (
            <>
              New to Cor1x?{" "}
              <a href="/signup" className="font-semibold text-accent underline-offset-4 hover:underline">
                Create an account
              </a>
            </>
          )}
        </p>

        {/* ── Footer strip ── */}
        <p className="mt-auto flex items-center justify-center gap-1.5 pt-8 text-[10px] font-bold uppercase tracking-[0.14em] text-paper-muted">
          <span aria-hidden className="h-1 w-1 rounded-full bg-accent" />
          Encrypted · Verified · Never shared
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

function TrustRow({
  icon,
  label,
  caption,
}: {
  icon: React.ReactNode;
  label: string;
  caption: string;
}) {
  return (
    <div className="flex items-center gap-2.5">
      {icon}
      <span className="text-[12px] font-bold text-paper">{label}</span>
      <span className="ml-auto text-[11px] text-paper-muted">{caption}</span>
    </div>
  );
}
