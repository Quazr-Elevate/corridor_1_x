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
 * Light-surface auth flow (per the light design variant): warm paper
 * background with a chartreuse pool top-left, ink text, bordered white
 * inputs, chartreuse pill CTA with a send glyph. Deliberately minimal —
 * no trust rows, no hint boxes; just what the task needs.
 *
 * Steps: form → otp (full-screen digit boxes) → business (signup only,
 * optional GSTIN/PAN verify). Logic identical to the dark build.
 */

// Light-theme atoms (kept as constants so all three steps stay in sync)
const pageBg: React.CSSProperties = {
  background:
    "radial-gradient(120% 60% at 0% 0%, rgba(196, 216, 46, 0.28), transparent 55%), #F4F1EC",
};

const inputCls =
  "h-12 w-full min-w-0 rounded-[10px] border border-[#D9D6CB] bg-white px-3.5 text-[15px] text-[#1A1C17] outline-none transition-[border-color,box-shadow] placeholder:text-[#A8A599] focus:border-[#B7C42C] focus:shadow-[0_0_0_3px_rgba(196,216,46,0.25)]";

const labelCls =
  "mb-2 block text-[11px] font-bold uppercase tracking-[0.1em] text-[#6E7266]";

const ctaEnabled =
  "flex h-[52px] items-center justify-center gap-2 rounded-[12px] bg-accent text-[15px] font-extrabold text-[#1A1C17] shadow-[0_8px_20px_-6px_rgba(140,155,30,0.5)] transition-all duration-150 hover:bg-accent-hover active:scale-[0.985] disabled:opacity-70";
const ctaDisabled =
  "flex h-[52px] items-center justify-center gap-2 rounded-[12px] bg-[#E4E1D6] text-[15px] font-extrabold text-[#9A978C]";

const accentText = "text-[#7E8C13]";

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
          title: "Sign up",
          eyebrow: "CREATE ACCOUNT",
          headLead: "One number.",
          headAccent: "One account.",
          subtitle: "Your name and mobile — that's all we need to start.",
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
      className="relative min-h-dvh overflow-y-auto text-[#1A1C17] safe-x"
      style={{
        ...pageBg,
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
              className="-ml-1.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] border border-[#D9D6CB] bg-white/70 text-[#1A1C17] transition-colors hover:bg-white"
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
                "-ml-1.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] border border-[#D9D6CB] bg-white/70 text-[#1A1C17] transition-colors hover:bg-white" +
                (step === "business" ? " invisible" : "")
              }
            >
              <ChevronLeft aria-hidden className="h-5 w-5" />
            </button>
          )}
          {/* Dark wordmark: the white asset filtered to ink. */}
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
            <div className="mt-6 inline-flex items-center gap-[7px] self-start rounded-full border border-[#D9D6CB] bg-white/70 px-3 py-1.5 text-[10px] font-extrabold tracking-[0.14em] text-[#6E7266]">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
              {copy.eyebrow}
            </div>

            <h1 className="mt-4 text-[27px] font-bold leading-[1.2] tracking-[-0.01em]" style={{ textWrap: "pretty" }}>
              {copy.headLead} <span className={accentText}>{copy.headAccent}</span>
            </h1>
            <p className="mt-2 text-[13.5px] leading-[1.55] text-[#6E7266]" style={{ textWrap: "pretty" }}>
              {copy.subtitle}
            </p>

            <div className="mt-7 flex flex-col gap-5">
              {nameNeeded && (
                <div>
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
                <div className="flex h-12 gap-2">
                  <span className="flex items-center rounded-[10px] border border-[#D9D6CB] bg-white px-[13px] text-[14px] font-bold text-[#1A1C17]">
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

              {nameNeeded ? (
                <label className="flex items-start gap-2 text-[12px] leading-[1.5] text-[#6E7266]">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    className="mt-0.5 h-3.5 w-3.5 rounded border-[#D9D6CB] accent-[#7E8C13]"
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
                <p className="text-[12px] leading-[1.5] text-[#6E7266]">
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

              <button
                type="button"
                onClick={sendOtp}
                disabled={!canSend || sending}
                className={canSend ? ctaEnabled : ctaDisabled}
              >
                {sending ? "Sending…" : "Send OTP"}
                {canSend && !sending && <Send aria-hidden className="h-4 w-4" />}
              </button>
              <p className="-mt-2 text-center text-[12.5px] text-[#6E7266]">{copy.ctaCaption}</p>

              {error && (
                <div className="space-y-1.5">
                  <p className="text-[13px] font-semibold text-[#C03A3A]">{error}</p>
                  {crossLink === "toLogin" && (
                    <a href="/login" className={accentText + " inline-flex items-center gap-1 text-[12px] font-semibold underline-offset-4 hover:underline"}>
                      Go to log in <ArrowRight aria-hidden className="h-3 w-3" />
                    </a>
                  )}
                  {crossLink === "toSignup" && (
                    <a href="/signup" className={accentText + " inline-flex items-center gap-1 text-[12px] font-semibold underline-offset-4 hover:underline"}>
                      Create an account <ArrowRight aria-hidden className="h-3 w-3" />
                    </a>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══ Step 2 — OTP ═══ */}
        {step === "otp" && (
          <div key="otp" className="flex flex-1 flex-col" style={stepAnim}>
            <h1 className="mt-6 text-[27px] font-bold leading-[1.2] tracking-[-0.01em]">
              Verify your number
            </h1>
            <p className="mt-2 text-[13.5px] leading-[1.55] text-[#6E7266]">
              We sent a {OTP_LENGTH}-digit code to{" "}
              <span className="font-bold text-[#1A1C17]">
                +91 {phone.slice(0, 5)} {phone.slice(5)}
              </span>
            </p>

            <div
              className="mt-7 flex justify-between gap-2"
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
                    "h-[52px] w-full min-w-0 rounded-[10px] border bg-white text-center text-[20px] font-bold text-[#1A1C17] outline-none transition-[border-color,box-shadow] " +
                    (otpError
                      ? "border-[#C03A3A]"
                      : d
                      ? "border-[#B7C42C] shadow-[0_0_0_3px_rgba(196,216,46,0.2)]"
                      : "border-[#D9D6CB] focus:border-[#B7C42C] focus:shadow-[0_0_0_3px_rgba(196,216,46,0.25)]")
                  }
                />
              ))}
            </div>

            {otpError && (
              <p className="mt-3 text-[13px] font-semibold text-[#C03A3A]">{otpError}</p>
            )}

            {devHint && (
              <p className="mt-4 text-[12px] text-[#6E7266]">
                <span className={accentText + " font-bold"}>Dev mode:</span> {devHint}
              </p>
            )}

            <p className="mt-5 text-[13px] text-[#6E7266]">
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

            {verifying && <p className="mt-4 text-[13px] text-[#6E7266]">Verifying…</p>}
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

        {/* Cross-mode link */}
        {step === "form" && (
          <p className="mt-6 text-center text-[12.5px] text-[#6E7266]">
            {mode === "signup" ? (
              <>
                Already have an account?{" "}
                <a href="/login" className={accentText + " font-semibold underline-offset-4 hover:underline"}>
                  Log in
                </a>
              </>
            ) : (
              <>
                New to Cor1x?{" "}
                <a href="/signup" className={accentText + " font-semibold underline-offset-4 hover:underline"}>
                  Create an account
                </a>
              </>
            )}
          </p>
        )}

        {/* Footer */}
        <p className="mt-auto flex items-center justify-center gap-1.5 pt-8 text-[10px] font-bold uppercase tracking-[0.14em] text-[#8B8F82]">
          <Lock aria-hidden className="h-3 w-3" />
          Encrypted · Verified · Never shared
        </p>
      </div>
    </main>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Step 3 — business identity (light theme)
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
      <div className="mt-6 inline-flex items-center gap-[7px] self-start rounded-full border border-[#D9D6CB] bg-white/70 px-3 py-1.5 text-[10px] font-extrabold tracking-[0.14em] text-[#6E7266]">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
        ACCOUNT CREATED · OPTIONAL
      </div>

      <h1 className="mt-4 text-[27px] font-bold leading-[1.2] tracking-[-0.01em]" style={{ textWrap: "pretty" }}>
        Add your <span className={accentText}>business identity.</span>
      </h1>
      <p className="mt-2 text-[13.5px] leading-[1.55] text-[#6E7266]" style={{ textWrap: "pretty" }}>
        Verify GSTIN or PAN now, or do it later from your profile.
      </p>

      {verified === null ? (
        <>
          <div className="mt-7 flex gap-1.5 rounded-[12px] border border-[#D9D6CB] bg-white/70 p-[5px]">
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
                  "h-11 flex-1 rounded-[9px] text-[14px] font-bold transition-all duration-200 " +
                  (tab === t
                    ? "bg-accent text-[#1A1C17] shadow-[0_2px_8px_-2px_rgba(140,155,30,0.5)]"
                    : "text-[#6E7266] hover:text-[#1A1C17]")
                }
              >
                {t === "gstin" ? "GSTIN" : "PAN only"}
              </button>
            ))}
          </div>

          <div className="mt-5">
            <label htmlFor="biz-id" className={labelCls}>
              {tab === "gstin" ? "GSTIN number" : "PAN number"}
            </label>
            <div className="flex gap-2">
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
                  "h-12 shrink-0 rounded-[10px] px-4 text-[13px] font-extrabold transition-colors " +
                  (valid && !busy
                    ? "bg-accent text-[#1A1C17] hover:bg-accent-hover"
                    : "bg-[#E4E1D6] text-[#9A978C]")
                }
              >
                {busy ? "Verifying…" : "Verify"}
              </button>
            </div>
          </div>

          {err && <p className="mt-3 text-[13px] font-semibold text-[#C03A3A]">{err}</p>}

          <button type="button" disabled className={ctaDisabled + " mt-7"}>
            Continue to dashboard <ArrowRight aria-hidden className="h-4 w-4" />
          </button>
          <p className="mt-2 text-center text-[12.5px] text-[#6E7266]">
            Verify your {tab === "gstin" ? "GSTIN" : "PAN"} to continue
          </p>
          <button
            type="button"
            onClick={onDone}
            className="mx-auto mt-4 text-[12.5px] font-semibold text-[#6E7266] underline-offset-4 hover:text-[#1A1C17] hover:underline"
          >
            Skip for now
          </button>
        </>
      ) : (
        <>
          <div className="mt-7 rounded-[12px] border border-[#B7C42C] bg-white p-5 shadow-[0_8px_24px_-8px_rgba(140,155,30,0.35)]">
            <div className="flex items-center gap-3">
              <span
                className="flex h-9 w-9 items-center justify-center rounded-full bg-accent"
                style={{ animation: "tickPop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both" }}
              >
                <Check aria-hidden className="h-5 w-5 text-[#1A1C17]" strokeWidth={3} />
              </span>
              <div style={{ animation: "fadeUp 0.45s ease 0.15s both" }}>
                <p className={accentText + " text-[10px] font-extrabold uppercase tracking-[0.14em]"}>
                  {verified.kind === "gstin" ? "GSTIN verified" : "PAN verified"}
                </p>
                <p className="mt-0.5 text-[15px] font-bold text-[#1A1C17]">{verified.name}</p>
              </div>
            </div>
            <div
              className="mt-4 space-y-1.5 border-t border-[#EAE7DD] pt-3 text-[12px] text-[#6E7266]"
              style={{ animation: "fadeUp 0.45s ease 0.25s both" }}
            >
              <p>
                <span className="uppercase tracking-[0.08em]">{verified.kind}</span> ·{" "}
                <span className="font-mono text-[#1A1C17]">{verified.id}</span>
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
            className={ctaEnabled + " mt-6"}
            style={{ animation: "fadeUp 0.45s ease 0.35s both" }}
          >
            Continue to dashboard <ArrowRight aria-hidden className="h-4 w-4" />
          </button>
        </>
      )}
    </div>
  );
}
