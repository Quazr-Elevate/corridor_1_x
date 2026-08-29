"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  Lock,
  Scale,
  ShieldCheck,
} from "lucide-react";
import { api, storeUserId, type GstinLookup } from "@/lib/api";
import { gstinRegex, panRegex, personNameField, phoneRegex } from "@/lib/validation";

type Mode = "login" | "signup";

interface Props {
  mode: Mode;
  onAuthed: (userId: string, isNew: boolean) => void;
}

const CONSENT_VERSION = "T-2026-08-29";
const OTP_LENGTH = 6;
const RESEND_SECONDS = 30;

/**
 * Auth flow — a three-step machine styled 1:1 after the design canvas.
 *
 *   form      name+phone+consent (signup) / phone (login)
 *   otp       full-screen "Verify your number" with digit boxes
 *             (design's dedicated OTP screen, not a modal)
 *   business  signup only — optional GSTIN/PAN verify with the design's
 *             segmented tabs; skippable, backed by /verify/{gstin,pan}
 *
 * Transitions: steps slide in from the right (stepIn) or left when going
 * back (stepBack). Wrong OTP shakes the row and rings the boxes in
 * danger. Business verify success pops a tick and rises the summary.
 * onAuthed fires after login verify, or after the business step is
 * completed/skipped on signup (the session cookie is already set).
 */
export function AuthShell({ mode, onAuthed }: Props) {
  type Step = "form" | "otp" | "business";
  const [step, setStep] = useState<Step>("form");
  const [dir, setDir] = useState<"fwd" | "back">("fwd");

  // ── form state ──
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [crossLink, setCrossLink] = useState<null | "toLogin" | "toSignup">(null);
  const [sending, setSending] = useState(false);
  const [devHint, setDevHint] = useState<string | undefined>(undefined);

  // ── otp state ──
  const [digits, setDigits] = useState<string[]>(() => Array(OTP_LENGTH).fill(""));
  const [otpError, setOtpError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [shaking, setShaking] = useState(false);
  const [resendIn, setResendIn] = useState(RESEND_SECONDS);
  const boxRefs = useRef<Array<HTMLInputElement | null>>([]);

  // ── business state (signup step 3) ──
  const [authedUser, setAuthedUser] = useState<{ userId: string; isNew: boolean } | null>(null);

  const phoneValid = phoneRegex.test(phone.trim());
  const nameNeeded = mode === "signup";
  const nameValid = !nameNeeded || personNameField.safeParse(fullName).success;
  const consentOk = !nameNeeded || consent;
  const canSend = phoneValid && nameValid && consentOk;

  // Resend countdown ticks only on the OTP step.
  useEffect(() => {
    if (step !== "otp" || resendIn <= 0) return;
    const iv = setInterval(() => setResendIn((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(iv);
  }, [step, resendIn]);

  const goto = (next: Step, direction: "fwd" | "back") => {
    setDir(direction);
    setStep(next);
  };

  // ── Step 1 → 2: send the OTP ─────────────────────────────────────────────

  const sendOtp = async () => {
    setError(null);
    setCrossLink(null);
    if (!phoneValid) return setError("Enter a valid 10-digit Indian mobile number");
    if (nameNeeded && !nameValid) return setError("Enter your full name (letters only)");
    if (nameNeeded && !consentOk)
      return setError("Please accept the Terms and Privacy Policy to continue");
    setSending(true);
    try {
      const res = await api.sendOtp({
        channel: "phone",
        value: phone.trim(),
        purpose: "phone",
        mode,
      });
      setDevHint(res.devHint);
      setDigits(Array(OTP_LENGTH).fill(""));
      setOtpError(null);
      setResendIn(RESEND_SECONDS);
      goto("otp", "fwd");
      setTimeout(() => boxRefs.current[0]?.focus(), 350);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not send code";
      setError(msg);
      if (mode === "signup" && /sign in instead/i.test(msg)) setCrossLink("toLogin");
      else if (mode === "login" && /sign up first/i.test(msg)) setCrossLink("toSignup");
    } finally {
      setSending(false);
    }
  };

  const resend = async () => {
    if (resendIn > 0) return;
    try {
      const res = await api.sendOtp({
        channel: "phone",
        value: phone.trim(),
        purpose: "phone",
        mode,
      });
      setDevHint(res.devHint);
      setDigits(Array(OTP_LENGTH).fill(""));
      setOtpError(null);
      setResendIn(RESEND_SECONDS);
      boxRefs.current[0]?.focus();
    } catch (err) {
      setOtpError(err instanceof Error ? err.message : "Could not resend code");
    }
  };

  // ── Step 2: verify + (signup) create the account ─────────────────────────

  const failOtp = (msg: string) => {
    setOtpError(msg);
    setShaking(true);
    setTimeout(() => setShaking(false), 450);
  };

  const submitCode = async (code: string) => {
    if (verifying) return;
    setVerifying(true);
    setOtpError(null);
    try {
      const res = await api.verifyOtp({
        otpId: "inline", // backend keys off mobile+code (MSG91 / stub)
        code,
        mobile: phone.trim(),
        mode,
      });
      if (!res.ok) {
        failOtp(res.error || "Incorrect code. Try again.");
        return;
      }

      if (!res.isNew && res.userId) {
        // Login — done.
        storeUserId(res.userId);
        onAuthed(res.userId, false);
        return;
      }

      // Signup — finalize the account, then offer the business step.
      const signed = await api.signup({
        fullName: fullName.trim(),
        consent: true,
        consentVersion: CONSENT_VERSION,
      });
      storeUserId(signed.userId);
      setAuthedUser({ userId: signed.userId, isNew: signed.isNew });
      goto("business", "fwd");
    } catch (err) {
      failOtp(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setVerifying(false);
    }
  };

  const onDigit = (i: number, raw: string) => {
    const v = raw.replace(/\D/g, "");
    if (otpError) setOtpError(null);
    if (!v) {
      setDigits((d) => {
        const next = [...d];
        next[i] = "";
        return next;
      });
      return;
    }
    // Paste of the whole code into any box
    if (v.length > 1) {
      const chars = v.slice(0, OTP_LENGTH).split("");
      const next = Array(OTP_LENGTH).fill("");
      chars.forEach((c, idx) => (next[idx] = c));
      setDigits(next);
      const last = Math.min(chars.length, OTP_LENGTH) - 1;
      boxRefs.current[last]?.focus();
      if (chars.length === OTP_LENGTH) void submitCode(chars.join(""));
      return;
    }
    setDigits((d) => {
      const next = [...d];
      next[i] = v;
      const full = next.every((c) => c !== "");
      if (full) void submitCode(next.join(""));
      return next;
    });
    if (i < OTP_LENGTH - 1) boxRefs.current[i + 1]?.focus();
  };

  const onDigitKey = (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !digits[i] && i > 0) {
      boxRefs.current[i - 1]?.focus();
    }
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

  const stepAnim = {
    animation: `${dir === "fwd" ? "stepIn" : "stepBack"} 0.4s cubic-bezier(0.16, 1, 0.3, 1) both`,
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
        {/* ── Top bar ── */}
        <div className="flex items-center gap-3 pt-4">
          {step === "form" ? (
            <Link
              href="/?intro=0"
              aria-label="Back"
              className="-ml-1.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-[6px] bg-ink-soft text-paper-soft shadow-[inset_0_0_0_1px_#3A3F38] transition-colors hover:text-paper"
            >
              <ChevronLeft aria-hidden className="h-5 w-5" />
            </Link>
          ) : (
            <button
              type="button"
              aria-label="Back"
              onClick={() => {
                // Business step is post-account; back returns to OTP is
                // meaningless — allow back only from the OTP step.
                if (step === "otp") goto("form", "back");
              }}
              className={
                "-ml-1.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-[6px] bg-ink-soft text-paper-soft shadow-[inset_0_0_0_1px_#3A3F38] transition-colors hover:text-paper" +
                (step === "business" ? " invisible" : "")
              }
            >
              <ChevronLeft aria-hidden className="h-5 w-5" />
            </button>
          )}
          <p className="text-[18px] font-bold tracking-tight text-paper">
            {step === "business" ? "Business identity" : copy.title}
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

        {step === "form" && (
          <FormStep
            key="form"
            stepAnim={stepAnim}
            copy={copy}
            nameNeeded={nameNeeded}
            fullName={fullName}
            setFullName={setFullName}
            phone={phone}
            setPhone={setPhone}
            consent={consent}
            setConsent={setConsent}
            error={error}
            setError={setError}
            crossLink={crossLink}
            canSend={canSend}
            sending={sending}
            sendOtp={sendOtp}
            mode={mode}
          />
        )}

        {step === "otp" && (
          <div key="otp" className="flex flex-1 flex-col" style={stepAnim}>
            <h1 className="mt-5 text-[26px] font-bold leading-[1.2] tracking-[-0.01em] text-paper">
              Verify your number
            </h1>
            <p className="mt-2 text-[13px] leading-[1.55] text-paper-muted">
              We sent a {OTP_LENGTH}-digit code to{" "}
              <span className="font-bold text-paper">
                +91 {phone.slice(0, 5)} {phone.slice(5)}
              </span>
            </p>

            {/* Digit boxes */}
            <div
              className="mt-6 flex justify-between gap-2"
              style={shaking ? { animation: "shakeX 0.45s ease" } : undefined}
            >
              {digits.map((d, i) => (
                <input
                  key={i}
                  ref={(el) => {
                    boxRefs.current[i] = el;
                  }}
                  value={d}
                  onChange={(e) => onDigit(i, e.target.value)}
                  onKeyDown={(e) => onDigitKey(i, e)}
                  inputMode="numeric"
                  autoComplete={i === 0 ? "one-time-code" : "off"}
                  aria-label={`Digit ${i + 1}`}
                  disabled={verifying}
                  className={
                    "h-[52px] w-full min-w-0 rounded-[8px] bg-ink-soft text-center text-[20px] font-bold text-paper outline-none transition-shadow " +
                    (otpError
                      ? "shadow-[inset_0_0_0_1.5px_#D64545]"
                      : d
                      ? "shadow-[inset_0_0_0_1.5px_rgba(196,216,46,0.5)]"
                      : "shadow-[inset_0_0_0_1px_#3A3F38] focus:shadow-[inset_0_0_0_1.5px_rgba(196,216,46,0.5)]")
                  }
                />
              ))}
            </div>

            {otpError && (
              <p className="mt-3 text-[13px] font-semibold text-danger">{otpError}</p>
            )}

            {devHint && (
              <div className="mt-4 flex items-center gap-2 rounded-[6px] border border-dashed border-line px-[13px] py-[11px] text-[11.5px] text-paper-muted">
                <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                <span>
                  <span className="font-bold text-accent">Dev mode:</span> {devHint}
                </span>
              </div>
            )}

            <p className="mt-5 text-[13px] text-paper-muted">
              Didn&apos;t get it?{" "}
              {resendIn > 0 ? (
                <span>Resend in {resendIn}s</span>
              ) : (
                <button
                  type="button"
                  onClick={resend}
                  className="font-semibold text-accent underline-offset-4 hover:underline"
                >
                  Resend code
                </button>
              )}
            </p>

            {verifying && (
              <p className="mt-4 text-[13px] text-paper-muted">Verifying…</p>
            )}
          </div>
        )}

        {step === "business" && authedUser && (
          <BusinessStep
            key="business"
            stepAnim={stepAnim}
            onDone={() => onAuthed(authedUser.userId, authedUser.isNew)}
          />
        )}

        {/* ── Cross-mode link (form step only) ── */}
        {step === "form" && (
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
        )}

        <p className="mt-auto flex items-center justify-center gap-1.5 pt-8 text-[10px] font-bold uppercase tracking-[0.14em] text-paper-muted">
          <span aria-hidden className="h-1 w-1 rounded-full bg-accent" />
          Encrypted · Verified · Never shared
        </p>
      </div>
    </main>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Step 1 — the form
// ═════════════════════════════════════════════════════════════════════════

function FormStep(props: {
  stepAnim: React.CSSProperties;
  copy: { eyebrow: string; headLead: string; headAccent: string; subtitle: string; ctaCaption: string };
  nameNeeded: boolean;
  fullName: string;
  setFullName: (v: string) => void;
  phone: string;
  setPhone: (v: string) => void;
  consent: boolean;
  setConsent: (v: boolean) => void;
  error: string | null;
  setError: (v: string | null) => void;
  crossLink: null | "toLogin" | "toSignup";
  canSend: boolean;
  sending: boolean;
  sendOtp: () => void;
  mode: Mode;
}) {
  const {
    stepAnim, copy, nameNeeded, fullName, setFullName, phone, setPhone,
    consent, setConsent, error, setError, crossLink, canSend, sending, sendOtp,
  } = props;

  return (
    <div className="flex flex-col" style={stepAnim}>
      <div className="mt-5 inline-flex items-center gap-[7px] self-start rounded-[6px] bg-ink-soft px-3 py-1.5 text-[10px] font-extrabold tracking-[0.14em] text-paper-soft shadow-[inset_0_0_0_1px_#3A3F38]">
        <span
          aria-hidden
          className="h-1.5 w-1.5 rounded-full bg-accent"
          style={{ animation: "glowPulse 1.8s ease infinite" }}
        />
        {copy.eyebrow}
      </div>

      <h1
        className="mt-3 text-[26px] font-bold leading-[1.2] tracking-[-0.01em] text-paper"
        style={{ textWrap: "pretty" }}
      >
        {copy.headLead} <span className="text-accent">{copy.headAccent}</span>
      </h1>
      <p className="mt-2 text-[13px] leading-[1.55] text-paper-muted" style={{ textWrap: "pretty" }}>
        {copy.subtitle}
      </p>

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
        <p className="-mt-1 text-center text-[12px] text-paper-muted">{copy.ctaCaption}</p>

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
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Step 3 — business identity (signup only, optional). Design's segmented
// GSTIN | PAN only tabs + field card + verify-in-place, then a success
// summary with tick pop. Backed by /verify/gstin and /verify/pan.
// ═════════════════════════════════════════════════════════════════════════

function BusinessStep({
  stepAnim,
  onDone,
}: {
  stepAnim: React.CSSProperties;
  onDone: () => void;
}) {
  const [tab, setTab] = useState<"gstin" | "pan">("gstin");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [verified, setVerified] = useState<null | {
    kind: "gstin" | "pan";
    id: string;
    name: string;
    lookup?: GstinLookup;
  }>(null);

  const valid =
    tab === "gstin"
      ? gstinRegex.test(value.trim().toUpperCase())
      : panRegex.test(value.trim().toUpperCase());

  const verify = async () => {
    setErr(null);
    const clean = value.trim().toUpperCase();
    if (!valid) {
      return setErr(
        tab === "gstin"
          ? "Enter a valid 15-character GSTIN"
          : "Enter a valid 10-character PAN",
      );
    }
    setBusy(true);
    try {
      if (tab === "gstin") {
        const res = await api.verifyGstin(clean);
        setVerified({ kind: "gstin", id: clean, name: res.lookup.legalName, lookup: res.lookup });
      } else {
        const res = await api.verifyPan(clean);
        setVerified({ kind: "pan", id: clean, name: res.name });
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Verification failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col" style={stepAnim}>
      <div className="mt-5 inline-flex items-center gap-[7px] self-start rounded-[6px] bg-ink-soft px-3 py-1.5 text-[10px] font-extrabold tracking-[0.14em] text-paper-soft shadow-[inset_0_0_0_1px_#3A3F38]">
        <span
          aria-hidden
          className="h-1.5 w-1.5 rounded-full bg-accent"
          style={{ animation: "glowPulse 1.8s ease infinite" }}
        />
        ACCOUNT CREATED · OPTIONAL STEP
      </div>

      <h1 className="mt-3 text-[26px] font-bold leading-[1.2] tracking-[-0.01em] text-paper" style={{ textWrap: "pretty" }}>
        You produced it. <span className="text-accent">Sell it directly.</span>
      </h1>
      <p className="mt-2 text-[13px] leading-[1.55] text-paper-muted" style={{ textWrap: "pretty" }}>
        Verify your GSTIN or PAN to trade with verified counterparties. You can
        also do this later from your profile.
      </p>

      {verified === null ? (
        <>
          {/* Segmented control */}
          <div className="mt-6 flex gap-1.5 rounded-[8px] bg-ink-soft p-[5px] shadow-[inset_0_0_0_1px_#3A3F38]">
            {(["gstin", "pan"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => {
                  setTab(t);
                  setValue("");
                  setErr(null);
                }}
                className={
                  "h-11 flex-1 rounded-[6px] text-[14px] font-bold transition-all duration-200 " +
                  (tab === t
                    ? "bg-ink-elevated text-accent shadow-[inset_0_0_0_1px_rgba(196,216,46,0.4)]"
                    : "text-paper-muted hover:text-paper-soft")
                }
              >
                {t === "gstin" ? "GSTIN" : "PAN only"}
              </button>
            ))}
          </div>

          {/* Field card */}
          <div className="mt-4 rounded-[10px] bg-ink-soft p-4 shadow-[inset_0_0_0_1px_#242724]">
            <label
              htmlFor="biz-id"
              className="mb-2 block text-[11px] font-bold uppercase tracking-[0.1em] text-paper-muted"
            >
              {tab === "gstin" ? "GSTIN number" : "PAN number"}
            </label>
            <div className="flex gap-2">
              <input
                id="biz-id"
                placeholder={tab === "gstin" ? "Enter GSTIN number" : "ABCDE1234F"}
                autoCapitalize="characters"
                autoComplete="off"
                spellCheck={false}
                maxLength={tab === "gstin" ? 15 : 10}
                value={value}
                onChange={(e) => {
                  setValue(e.target.value.toUpperCase());
                  if (err) setErr(null);
                }}
                className="h-12 min-w-0 flex-1 rounded-[6px] bg-ink px-3.5 text-[14px] uppercase tracking-[0.05em] text-paper shadow-[inset_0_0_0_1px_#3A3F38] outline-none transition-shadow placeholder:normal-case placeholder:tracking-normal placeholder:text-paper-muted/60 focus:shadow-[inset_0_0_0_1px_rgba(196,216,46,0.5)]"
              />
              <button
                type="button"
                onClick={verify}
                disabled={!valid || busy}
                className={
                  "h-12 shrink-0 rounded-[6px] px-4 text-[13px] font-extrabold transition-colors " +
                  (valid && !busy
                    ? "bg-accent text-accent-fg hover:bg-accent-hover"
                    : "bg-ink-elevated text-paper-muted")
                }
              >
                {busy ? "Verifying…" : "Verify"}
              </button>
            </div>
            <p className="mt-2 text-[11.5px] text-paper-muted">
              {tab === "gstin"
                ? "15 characters — e.g. 27ABCDE1234F1Z5"
                : "10 characters — company or proprietor PAN"}
            </p>
          </div>

          {err && <p className="mt-3 text-[13px] font-semibold text-danger">{err}</p>}

          <div className="mt-3 flex items-center gap-2 rounded-[6px] border border-dashed border-line px-[13px] py-[11px] text-[11.5px] leading-[1.5] text-paper-muted">
            <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
            {tab === "gstin"
              ? "Enter your GSTIN and tap Verify — we'll fetch your business details in under a second."
              : "PAN-only works for proprietors without GST registration."}
          </div>

          {/* Disabled continue + skip */}
          <button
            type="button"
            disabled
            className="mt-5 flex h-[52px] items-center justify-center gap-1.5 rounded-[6px] bg-ink-soft text-[15px] font-extrabold text-paper-muted shadow-[inset_0_0_0_1px_#3A3F38]"
          >
            Continue to dashboard <ArrowRight aria-hidden className="h-4 w-4" />
          </button>
          <p className="mt-2 text-center text-[12px] text-paper-muted">
            Verify your {tab === "gstin" ? "GSTIN" : "PAN"} to continue
          </p>
          <button
            type="button"
            onClick={onDone}
            className="mx-auto mt-4 text-[12px] font-semibold text-paper-muted underline-offset-4 hover:text-paper hover:underline"
          >
            Skip for now — I&apos;ll do this from my profile
          </button>
        </>
      ) : (
        <>
          {/* Success card — tick pop + rising summary */}
          <div className="mt-6 rounded-[10px] bg-ink-soft p-5 shadow-[inset_0_0_0_1px_rgba(196,216,46,0.35)]">
            <div className="flex items-center gap-3">
              <span
                className="flex h-9 w-9 items-center justify-center rounded-full bg-accent"
                style={{ animation: "tickPop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both" }}
              >
                <Check aria-hidden className="h-5 w-5 text-accent-fg" strokeWidth={3} />
              </span>
              <div style={{ animation: "fadeUp 0.45s ease 0.15s both" }}>
                <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-accent">
                  {verified.kind === "gstin" ? "GSTIN verified" : "PAN verified"}
                </p>
                <p className="mt-0.5 text-[15px] font-bold text-paper">{verified.name}</p>
              </div>
            </div>
            <div
              className="mt-4 space-y-1.5 border-t border-line-soft pt-3 text-[12px] text-paper-muted"
              style={{ animation: "fadeUp 0.45s ease 0.25s both" }}
            >
              <p>
                <span className="uppercase tracking-[0.08em]">{verified.kind}</span>{" "}
                · <span className="font-mono text-paper-soft">{verified.id}</span>
              </p>
              {verified.lookup?.address && (
                <p>
                  {verified.lookup.address.city}, {verified.lookup.address.state} ·{" "}
                  {verified.lookup.address.pincode}
                </p>
              )}
              {verified.lookup?.businessType && <p>{verified.lookup.businessType}</p>}
            </div>
          </div>

          <button
            type="button"
            onClick={onDone}
            className="mt-5 flex h-[52px] items-center justify-center gap-1.5 rounded-[6px] bg-accent text-[15px] font-extrabold text-accent-fg shadow-[0_6px_16px_rgba(0,0,0,0.35)] transition-all duration-150 hover:bg-accent-hover active:scale-[0.985]"
            style={{ animation: "fadeUp 0.45s ease 0.35s both" }}
          >
            Continue to dashboard <ArrowRight aria-hidden className="h-4 w-4" />
          </button>
        </>
      )}
    </div>
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
