"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Check, ChevronLeft, Lock, Send } from "lucide-react";
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

/*
 * Light auth — "gradient accent" concept. Off-white paper (#FAFAF8) with a
 * large, diffused lime pool at the upper-right; charcoal type (#171917);
 * restrained lime accents; a faint corridor route/node trace in the
 * background as continuity with the splash journey (flight → destination →
 * X → login: "I just arrived at the Corridor").
 *
 * Entry is a staggered composition (top bar → badge → headline → copy →
 * field → CTA → footer, ~100ms apart). Steps slide via stepIn/stepBack.
 * Flow logic identical to previous builds.
 */

// ── Shared light atoms ───────────────────────────────────────────────────────

const pageBg: React.CSSProperties = {
  background:
    "radial-gradient(110% 55% at 78% -8%, rgba(196, 216, 46, 0.20), rgba(196, 216, 46, 0.06) 45%, transparent 65%), #FAFAF8",
};

const inputCls =
  "h-[54px] w-full min-w-0 rounded-[12px] border border-[#D9DDD7] bg-white px-4 text-[17px] text-[#171917] outline-none transition-[border-color,box-shadow] duration-200 placeholder:text-[#AEB3AA] focus:border-[#B7C42C] focus:shadow-[0_0_0_3px_rgba(196,216,46,0.18)]";

const labelCls =
  "mb-2.5 block text-[12px] font-bold uppercase tracking-[0.1em] text-[#747970]";

const ctaEnabled =
  "flex h-14 items-center justify-center gap-2 rounded-[13px] bg-accent text-[17px] font-bold text-[#171917] shadow-[0_10px_24px_-10px_rgba(150,165,30,0.45)] transition-all duration-150 hover:bg-accent-hover active:scale-[0.98] disabled:opacity-70";
const ctaDisabled =
  "flex h-14 items-center justify-center gap-2 rounded-[13px] bg-[#ECEDE6] text-[17px] font-bold text-[#A2A69C]";

const accentText = "text-[#7E8C13]";

// Staggered entry — delays per the composition spec.
const rise = (delay: number): React.CSSProperties => ({
  animation: `fadeUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s both`,
});

export function AuthShell({ mode, onAuthed }: Props) {
  type Step = "form" | "otp" | "business";
  const [step, setStep] = useState<Step>("form");
  const [dir, setDir] = useState<"fwd" | "back">("fwd");

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [crossLink, setCrossLink] = useState<null | "toLogin" | "toSignup">(null);
  const [sending, setSending] = useState(false);
  const [devHint, setDevHint] = useState<string | undefined>(undefined);

  const [digits, setDigits] = useState<string[]>(() => Array(OTP_LENGTH).fill(""));
  const [otpError, setOtpError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [shaking, setShaking] = useState(false);
  const [resendIn, setResendIn] = useState(RESEND_SECONDS);
  const boxRefs = useRef<Array<HTMLInputElement | null>>([]);

  const [authedUser, setAuthedUser] = useState<{ userId: string; isNew: boolean } | null>(null);

  const phoneValid = phoneRegex.test(phone.trim());
  const nameNeeded = mode === "signup";
  const nameValid = !nameNeeded || personNameField.safeParse(fullName).success;
  const consentOk = !nameNeeded || consent;
  const canSend = phoneValid && nameValid && consentOk;

  useEffect(() => {
    if (step !== "otp" || resendIn <= 0) return;
    const iv = setInterval(() => setResendIn((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(iv);
  }, [step, resendIn]);

  const goto = (next: Step, direction: "fwd" | "back") => {
    setDir(direction);
    setStep(next);
  };

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
        otpId: "inline",
        code,
        mobile: phone.trim(),
        mode,
      });
      if (!res.ok) {
        failOtp(res.error || "Incorrect code. Try again.");
        return;
      }
      if (!res.isNew && res.userId) {
        storeUserId(res.userId);
        onAuthed(res.userId, false);
        return;
      }
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
      if (next.every((c) => c !== "")) void submitCode(next.join(""));
      return next;
    });
    if (i < OTP_LENGTH - 1) boxRefs.current[i + 1]?.focus();
  };

  const onDigitKey = (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !digits[i] && i > 0) boxRefs.current[i - 1]?.focus();
  };

  const copy =
    mode === "signup"
      ? {
          eyebrow: "CREATE ACCOUNT",
          headLead: "One number.",
          headAccent: "One account.",
          subtitle: "Your name and mobile — that's all we need to start.",
          ctaCaption: canSend
            ? "We'll text a one-time code to verify"
            : "Fill your name and mobile to continue",
        }
      : {
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
      className="relative min-h-dvh overflow-hidden text-[#171917] safe-x"
      style={{
        ...pageBg,
        paddingTop: "max(env(safe-area-inset-top), 24px)",
        paddingBottom: "max(env(safe-area-inset-bottom), 24px)",
      }}
    >
      {/* Corridor trace — the splash journey's residue: a thin curved route
          with nodes arriving at a small X, upper-right, barely-there. */}
      <CorridorTrace />

      <div className="relative mx-auto flex min-h-[calc(100dvh-48px)] w-full max-w-[440px] flex-col px-6 sm:max-w-md lg:max-w-[480px]">
        {/* ── Top bar ── */}
        <div className="flex items-center gap-3 pt-3" style={rise(0.1)}>
          {step === "form" ? (
            <Link
              href="/?intro=0"
              aria-label="Back"
              className="-ml-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] border border-[#D9DDD7] bg-white/60 text-[#171917] transition-all duration-150 hover:bg-white active:scale-95"
            >
              <ChevronLeft aria-hidden className="h-5 w-5" />
            </Link>
          ) : (
            <button
              type="button"
              aria-label="Back"
              onClick={() => {
                if (step === "otp") goto("form", "back");
              }}
              className={
                "-ml-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] border border-[#D9DDD7] bg-white/60 text-[#171917] transition-all duration-150 hover:bg-white active:scale-95" +
                (step === "business" ? " invisible" : "")
              }
            >
              <ChevronLeft aria-hidden className="h-5 w-5" />
            </button>
          )}
          <Image
            src="/brand/wordmark.png"
            alt="Corridor One X"
            width={1583}
            height={173}
            priority
            className="ml-auto w-[128px] select-none brightness-0 opacity-90"
          />
        </div>

        {/* ═══ Step 1 — form ═══ */}
        {step === "form" && (
          <div key="form" className="flex flex-col" style={stepAnim}>
            <div
              className="mt-8 inline-flex items-center gap-2 self-start rounded-full border border-[#D9DDD7] bg-white/60 px-3.5 py-2 text-[11px] font-bold uppercase tracking-[0.14em] text-[#5C6058]"
              style={rise(0.2)}
            >
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
              {copy.eyebrow}
            </div>

            <h1
              className="mt-6 text-[clamp(30px,9.5vw,38px)] font-bold leading-[1.12] tracking-[-0.02em]"
              style={{ textWrap: "balance", ...rise(0.25) }}
            >
              {copy.headLead}
              <br />
              <span className={accentText}>{copy.headAccent}</span>
            </h1>
            <p
              className="mt-3 max-w-[320px] text-[17px] leading-[1.55] text-[#747970]"
              style={{ textWrap: "pretty", ...rise(0.35) }}
            >
              {copy.subtitle}
            </p>

            <div className="mt-10 flex flex-col" style={rise(0.45)}>
              {nameNeeded && (
                <div className="mb-6">
                  <label htmlFor="auth-name" className={labelCls}>
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
                    className={inputCls}
                  />
                </div>
              )}

              <div>
                <label htmlFor="auth-phone" className={labelCls}>
                  Phone number
                </label>
                <div className="flex h-[54px] gap-2.5">
                  <span className="flex items-center rounded-[12px] border border-[#D9DDD7] bg-white px-4 text-[16px] font-bold text-[#171917]">
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
                    className={inputCls + " flex-1 tracking-wide"}
                  />
                </div>
              </div>

              <div className="mt-7">
                {nameNeeded ? (
                  <label className="flex items-start gap-2.5 text-[13px] leading-[1.6] text-[#5C6058]">
                    <input
                      type="checkbox"
                      checked={consent}
                      onChange={(e) => setConsent(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-[#D9DDD7] accent-[#7E8C13]"
                    />
                    <span>
                      I accept Cor1x&apos;s{" "}
                      <a href="/terms" target="_blank" className={accentText + " font-semibold underline-offset-4 hover:underline"}>
                        Terms
                      </a>{" "}
                      and{" "}
                      <a href="/privacy" target="_blank" className={accentText + " font-semibold underline-offset-4 hover:underline"}>
                        Privacy Policy
                      </a>
                      .
                    </span>
                  </label>
                ) : (
                  <p className="max-w-[300px] text-[13px] leading-[1.6] text-[#5C6058]">
                    By continuing you agree to Cor1x&apos;s{" "}
                    <a href="/terms" target="_blank" className={accentText + " font-semibold underline-offset-4 hover:underline"}>
                      Terms
                    </a>{" "}
                    and{" "}
                    <a href="/privacy" target="_blank" className={accentText + " font-semibold underline-offset-4 hover:underline"}>
                      Privacy Policy
                    </a>
                    .
                  </p>
                )}
              </div>
            </div>

            <div className="mt-7 flex flex-col" style={rise(0.55)}>
              <button
                type="button"
                onClick={sendOtp}
                disabled={!canSend || sending}
                className={canSend ? ctaEnabled : ctaDisabled}
              >
                {sending ? "Sending…" : "Send OTP"}
                {canSend && !sending && <Send aria-hidden className="h-[18px] w-[18px]" />}
              </button>
              <p className="mt-[18px] text-center text-[13px] text-[#747970]">
                {copy.ctaCaption}
              </p>

              {error && (
                <div className="mt-3 space-y-1.5">
                  <p className="text-[13px] font-semibold text-[#C03A3A]">{error}</p>
                  {crossLink === "toLogin" && (
                    <a href="/login" className={accentText + " inline-flex items-center gap-1 text-[13px] font-semibold underline-offset-4 hover:underline"}>
                      Go to log in <ArrowRight aria-hidden className="h-3 w-3" />
                    </a>
                  )}
                  {crossLink === "toSignup" && (
                    <a href="/signup" className={accentText + " inline-flex items-center gap-1 text-[13px] font-semibold underline-offset-4 hover:underline"}>
                      Create an account <ArrowRight aria-hidden className="h-3 w-3" />
                    </a>
                  )}
                </div>
              )}

              <p className="mt-9 text-center text-[14px] text-[#747970]">
                {mode === "signup" ? (
                  <>
                    Already have an account?{" "}
                    <a href="/login" className={accentText + " font-semibold underline-offset-4 transition-opacity hover:underline active:opacity-70"}>
                      Log in
                    </a>
                  </>
                ) : (
                  <>
                    New to Cor1x?{" "}
                    <a href="/signup" className={accentText + " font-semibold underline-offset-4 transition-opacity hover:underline active:opacity-70"}>
                      Create an account
                    </a>
                  </>
                )}
              </p>
            </div>
          </div>
        )}

        {/* ═══ Step 2 — OTP ═══ */}
        {step === "otp" && (
          <div key="otp" className="flex flex-1 flex-col" style={stepAnim}>
            <h1 className="mt-8 text-[clamp(28px,8.5vw,34px)] font-bold leading-[1.12] tracking-[-0.02em]">
              Verify your number
            </h1>
            <p className="mt-3 text-[17px] leading-[1.55] text-[#747970]">
              We sent a {OTP_LENGTH}-digit code to{" "}
              <span className="font-bold text-[#171917]">
                +91 {phone.slice(0, 5)} {phone.slice(5)}
              </span>
            </p>

            <div
              className="mt-8 flex justify-between gap-2"
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
                    "h-14 w-full min-w-0 rounded-[12px] border bg-white text-center text-[22px] font-bold text-[#171917] outline-none transition-[border-color,box-shadow] duration-200 " +
                    (otpError
                      ? "border-[#C03A3A]"
                      : d
                      ? "border-[#B7C42C] shadow-[0_0_0_3px_rgba(196,216,46,0.15)]"
                      : "border-[#D9DDD7] focus:border-[#B7C42C] focus:shadow-[0_0_0_3px_rgba(196,216,46,0.18)]")
                  }
                />
              ))}
            </div>

            {otpError && (
              <p className="mt-3 text-[13px] font-semibold text-[#C03A3A]">{otpError}</p>
            )}

            {devHint && (
              <p className="mt-5 text-[13px] text-[#747970]">
                <span className={accentText + " font-bold"}>Dev mode:</span> {devHint}
              </p>
            )}

            <p className="mt-6 text-[14px] text-[#747970]">
              Didn&apos;t get it?{" "}
              {resendIn > 0 ? (
                <span>Resend in {resendIn}s</span>
              ) : (
                <button
                  type="button"
                  onClick={resend}
                  className={accentText + " font-semibold underline-offset-4 hover:underline"}
                >
                  Resend code
                </button>
              )}
            </p>

            {verifying && <p className="mt-4 text-[13px] text-[#747970]">Verifying…</p>}
          </div>
        )}

        {/* ═══ Step 3 — business (signup only, optional) ═══ */}
        {step === "business" && authedUser && (
          <BusinessStep
            key="business"
            stepAnim={stepAnim}
            onDone={() => onAuthed(authedUser.userId, authedUser.isNew)}
          />
        )}

        {/* Security footer */}
        <p
          className="mt-auto flex items-center justify-center gap-2 pt-9 text-[11px] font-bold uppercase tracking-[0.16em] text-[#9B9F94]"
          style={rise(0.65)}
        >
          <Lock aria-hidden className="h-3 w-3" />
          Encrypted · Verified · Never shared
        </p>
      </div>
    </main>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Corridor trace — thin curved route lines + nodes arriving at a small X,
// echoing the splash journey. Upper-right, extremely low opacity.
// ═════════════════════════════════════════════════════════════════════════

function CorridorTrace() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 280 320"
      className="pointer-events-none absolute -right-4 -top-2 h-[300px] w-[260px] opacity-[0.45]"
      fill="none"
    >
      <defs>
        <linearGradient id="ctRoute" x1="1" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#C4D82E" stopOpacity="0.5" />
          <stop offset="70%" stopColor="#C4D82E" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#C4D82E" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="ctRoute2" x1="1" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#9BA982" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#9BA982" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Primary route — sweeping down the right edge */}
      <path
        d="M300,20 C230,45 200,110 170,160 C148,196 140,230 148,278"
        stroke="url(#ctRoute)"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      {/* Secondary fainter route */}
      <path
        d="M310,90 C250,110 230,160 208,200 C194,226 192,244 200,272"
        stroke="url(#ctRoute2)"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeDasharray="1 8"
      />

      {/* Waypoint nodes along the primary route */}
      <circle cx="228" cy="46" r="3" fill="#C4D82E" fillOpacity="0.55" />
      <circle cx="181" cy="140" r="2.5" fill="#C4D82E" fillOpacity="0.4" />
      <circle cx="145" cy="222" r="2.5" fill="#C4D82E" fillOpacity="0.3" />

      {/* Arrival X-node — journey's end, kept clear of the content column */}
      <g transform="translate(150, 282)" opacity="0.45">
        <circle r="11" stroke="#C4D82E" strokeOpacity="0.4" strokeWidth="1" />
        <path
          d="M-4,-4 L4,4 M4,-4 L-4,4"
          stroke="#7E8C13"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </g>

      {/* Sparse geometric accents */}
      <circle cx="252" cy="150" r="1.5" fill="#9BA982" fillOpacity="0.5" />
      <circle cx="222" cy="238" r="1.5" fill="#9BA982" fillOpacity="0.4" />
      <rect x="238" y="196" width="7" height="7" rx="1.5" stroke="#C4D82E" strokeOpacity="0.25" strokeWidth="1" transform="rotate(18 241 199)" />
    </svg>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Step 3 — business identity (light)
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
        tab === "gstin" ? "Enter a valid 15-character GSTIN" : "Enter a valid 10-character PAN",
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
      <div className="mt-8 inline-flex items-center gap-2 self-start rounded-full border border-[#D9DDD7] bg-white/60 px-3.5 py-2 text-[11px] font-bold uppercase tracking-[0.14em] text-[#5C6058]">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
        ACCOUNT CREATED · OPTIONAL
      </div>

      <h1
        className="mt-6 text-[clamp(28px,8.5vw,34px)] font-bold leading-[1.12] tracking-[-0.02em]"
        style={{ textWrap: "balance" }}
      >
        Add your <span className={accentText}>business identity.</span>
      </h1>
      <p className="mt-3 max-w-[320px] text-[17px] leading-[1.55] text-[#747970]" style={{ textWrap: "pretty" }}>
        Verify GSTIN or PAN now, or do it later from your profile.
      </p>

      {verified === null ? (
        <>
          <div className="mt-8 flex gap-1.5 rounded-[14px] border border-[#D9DDD7] bg-white/60 p-[5px]">
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
                  "h-11 flex-1 rounded-[10px] text-[14px] font-bold transition-all duration-200 " +
                  (tab === t
                    ? "bg-accent text-[#171917] shadow-[0_2px_10px_-2px_rgba(150,165,30,0.4)]"
                    : "text-[#747970] hover:text-[#171917]")
                }
              >
                {t === "gstin" ? "GSTIN" : "PAN only"}
              </button>
            ))}
          </div>

          <div className="mt-6">
            <label htmlFor="biz-id" className={labelCls}>
              {tab === "gstin" ? "GSTIN number" : "PAN number"}
            </label>
            <div className="flex gap-2.5">
              <input
                id="biz-id"
                placeholder={tab === "gstin" ? "27ABCDE1234F1Z5" : "ABCDE1234F"}
                autoCapitalize="characters"
                autoComplete="off"
                spellCheck={false}
                maxLength={tab === "gstin" ? 15 : 10}
                value={value}
                onChange={(e) => {
                  setValue(e.target.value.toUpperCase());
                  if (err) setErr(null);
                }}
                className={inputCls + " flex-1 uppercase tracking-[0.05em] placeholder:normal-case placeholder:tracking-normal"}
              />
              <button
                type="button"
                onClick={verify}
                disabled={!valid || busy}
                className={
                  "h-[54px] shrink-0 rounded-[12px] px-5 text-[14px] font-bold transition-colors " +
                  (valid && !busy
                    ? "bg-accent text-[#171917] hover:bg-accent-hover"
                    : "bg-[#ECEDE6] text-[#A2A69C]")
                }
              >
                {busy ? "Verifying…" : "Verify"}
              </button>
            </div>
          </div>

          {err && <p className="mt-3 text-[13px] font-semibold text-[#C03A3A]">{err}</p>}

          <button type="button" disabled className={ctaDisabled + " mt-8"}>
            Continue to dashboard <ArrowRight aria-hidden className="h-4 w-4" />
          </button>
          <p className="mt-[18px] text-center text-[13px] text-[#747970]">
            Verify your {tab === "gstin" ? "GSTIN" : "PAN"} to continue
          </p>
          <button
            type="button"
            onClick={onDone}
            className="mx-auto mt-6 text-[14px] font-semibold text-[#747970] underline-offset-4 transition-opacity hover:text-[#171917] hover:underline active:opacity-70"
          >
            Skip for now
          </button>
        </>
      ) : (
        <>
          <div className="mt-8 rounded-[14px] border border-[#B7C42C] bg-white p-5 shadow-[0_12px_28px_-12px_rgba(150,165,30,0.35)]">
            <div className="flex items-center gap-3">
              <span
                className="flex h-10 w-10 items-center justify-center rounded-full bg-accent"
                style={{ animation: "tickPop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both" }}
              >
                <Check aria-hidden className="h-5 w-5 text-[#171917]" strokeWidth={3} />
              </span>
              <div style={{ animation: "fadeUp 0.45s ease 0.15s both" }}>
                <p className={accentText + " text-[11px] font-bold uppercase tracking-[0.14em]"}>
                  {verified.kind === "gstin" ? "GSTIN verified" : "PAN verified"}
                </p>
                <p className="mt-0.5 text-[16px] font-bold text-[#171917]">{verified.name}</p>
              </div>
            </div>
            <div
              className="mt-4 space-y-1.5 border-t border-[#EEF0EA] pt-3.5 text-[13px] text-[#747970]"
              style={{ animation: "fadeUp 0.45s ease 0.25s both" }}
            >
              <p>
                <span className="uppercase tracking-[0.08em]">{verified.kind}</span> ·{" "}
                <span className="font-mono text-[#171917]">{verified.id}</span>
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
            className={ctaEnabled + " mt-7"}
            style={{ animation: "fadeUp 0.45s ease 0.35s both" }}
          >
            Continue to dashboard <ArrowRight aria-hidden className="h-4 w-4" />
          </button>
        </>
      )}
    </div>
  );
}
