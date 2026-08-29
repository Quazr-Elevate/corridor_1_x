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

// Ambient wash — a wide arc of lime sweeping the whole top edge and
// feathering down into the paper, like light through a doorway. Two layers:
// a saturated crest hugging the very top, and a broad soft falloff beneath
// it so there is no visible seam ("blended, not painted on").
const pageBg: React.CSSProperties = {
  background: [
    "radial-gradient(130% 62% at 22% -38%, rgba(206, 222, 40, 0.80) 52%, rgba(206, 222, 40, 0.28) 68%, rgba(206, 222, 40, 0) 80%)",
    "radial-gradient(170% 80% at 60% -48%, rgba(196, 216, 46, 0.22) 55%, rgba(196, 216, 46, 0.07) 72%, rgba(196, 216, 46, 0) 85%)",
    "#FAFAF8",
  ].join(", "),
};

const inputCls =
  "h-[54px] w-full min-w-0 rounded-[12px] border border-[#D9DDD7] bg-white px-4 text-[17px] text-[#171917] outline-none transition-[border-color,box-shadow] duration-200 placeholder:text-[#AEB3AA] focus:border-[#B7C42C] focus:shadow-[0_0_0_3px_rgba(196,216,46,0.18)]";

const labelCls =
  "mb-2.5 block text-[12px] font-bold uppercase tracking-[0.1em] text-[#747970]";

// CTA — gradient lime slab with a soft outer glow (the reference's smudge
// of light under the button) and the send glyph pinned to the right edge.
const ctaEnabled =
  "relative flex h-[58px] items-center justify-center rounded-[16px] text-[18px] font-bold text-[#171917] transition-all duration-150 active:scale-[0.98] disabled:opacity-70";
const ctaEnabledStyle: React.CSSProperties = {
  background:
    "linear-gradient(180deg, #DCE84A 0%, #C9DB2A 45%, #BCCB08 100%)",
  boxShadow:
    "0 18px 44px -14px rgba(188, 203, 8, 0.55), 0 6px 16px -6px rgba(150, 165, 30, 0.35), inset 0 1px 0 rgba(255,255,255,0.35)",
};
const ctaDisabled =
  "flex h-[58px] items-center justify-center gap-2 rounded-[16px] bg-[#ECEDE6] text-[18px] font-bold text-[#A2A69C]";

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
              {copy.headLead}{" "}
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
                style={canSend ? ctaEnabledStyle : undefined}
              >
                {sending ? "Sending…" : "Send OTP"}
                {canSend && !sending && (
                  <Send
                    aria-hidden
                    className="absolute right-6 top-1/2 h-5 w-5 -translate-y-1/2"
                  />
                )}
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
      viewBox="0 0 340 560"
      className="pointer-events-none absolute -right-10 top-[120px] h-[520px] w-[320px]"
      fill="none"
    >
      {/* Dotted orbital arcs — the reference's network trace: big, airy,
          dashed curves crossing on the right side with solid lime nodes. */}
      <path
        d="M330,10 C220,60 150,170 140,290 C132,380 160,460 240,520"
        stroke="#C4D82E"
        strokeOpacity="0.30"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeDasharray="2 9"
      />
      <path
        d="M345,140 C260,150 195,220 185,310 C177,382 200,440 260,480"
        stroke="#C4D82E"
        strokeOpacity="0.22"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeDasharray="2 11"
      />
      <path
        d="M340,300 C290,290 240,320 225,370"
        stroke="#C4D82E"
        strokeOpacity="0.18"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeDasharray="2 9"
      />

      {/* Solid lime nodes at arc intersections */}
      <circle cx="196" cy="118" r="5" fill="#C4D82E" fillOpacity="0.55" />
      <circle cx="141" cy="300" r="4" fill="#C4D82E" fillOpacity="0.45" />
      <circle cx="257" cy="404" r="5" fill="#C4D82E" fillOpacity="0.5" />
      <circle cx="304" cy="212" r="3.5" fill="#C4D82E" fillOpacity="0.35" />
      <circle cx="232" cy="482" r="3" fill="#C4D82E" fillOpacity="0.35" />
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
            className={ctaEnabled + " mt-7 gap-2"}
            style={{ ...ctaEnabledStyle, animation: "fadeUp 0.45s ease 0.35s both" }}
          >
            Continue to dashboard <ArrowRight aria-hidden className="h-4 w-4" />
          </button>
        </>
      )}
    </div>
  );
}
