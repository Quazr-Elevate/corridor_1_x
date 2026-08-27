"use client";

import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { AmbientBackground } from "@/components/brand/AmbientBackground";
import { Button } from "@/components/ui/Button";
import { FieldWithAction } from "@/components/ui/FieldWithAction";
import { api, storeUserId } from "@/lib/api";
import { phoneRegex } from "@/lib/validation";

const OTP_LENGTH = 6;
const EASE = [0.22, 1, 0.36, 1] as const;

export function AuthClient() {
  const router = useRouter();
  // Mobile
  const [mobile, setMobile] = useState("");
  const [mobileError, setMobileError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  // OTP session (populated after Send OTP succeeds)
  const [otpId, setOtpId] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [devHint, setDevHint] = useState<string | null>(null);

  // OTP entry
  const [digits, setDigits] = useState<string[]>(() => Array(OTP_LENGTH).fill(""));
  const [otpError, setOtpError] = useState<string | null>(null);
  const [entering, setEntering] = useState(false);
  const otpRefs = useRef<Array<HTMLInputElement | null>>([]);

  // Result
  const [done, setDone] = useState<null | { isNew: boolean }>(null);

  const mobileValid = phoneRegex.test(mobile.trim());
  const otpCode = digits.join("");
  const otpComplete = otpCode.length === OTP_LENGTH && !digits.includes("");

  useEffect(() => {
    if (sentTo) {
      const t = setTimeout(() => otpRefs.current[0]?.focus(), 120);
      return () => clearTimeout(t);
    }
  }, [sentTo]);

  const handleSendOtp = async () => {
    setMobileError(null);
    if (!mobileValid) {
      setMobileError("Enter a valid 10-digit mobile number");
      return;
    }
    setSending(true);
    try {
      const res = await api.sendOtp({
        channel: "phone",
        value: mobile.trim(),
        purpose: "phone",
      });
      setOtpId(res.otpId);
      setSentTo(res.destination);
      setDevHint(res.devHint ?? null);
      setDigits(Array(OTP_LENGTH).fill(""));
      setOtpError(null);
    } catch (err) {
      setMobileError(err instanceof Error ? err.message : "Could not send code");
    } finally {
      setSending(false);
    }
  };

  const changeMobile = () => {
    setSentTo(null);
    setOtpId(null);
    setDigits(Array(OTP_LENGTH).fill(""));
    setOtpError(null);
    setDevHint(null);
  };

  const setDigit = (i: number, v: string) => {
    setDigits((prev) => {
      const next = [...prev];
      next[i] = v;
      return next;
    });
  };

  const handleDigitChange = (i: number) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, "");
    if (otpError) setOtpError(null);
    if (!raw) {
      setDigit(i, "");
      return;
    }
    if (raw.length === 1) {
      setDigit(i, raw);
      if (i < OTP_LENGTH - 1) otpRefs.current[i + 1]?.focus();
    } else {
      const chars = raw.slice(0, OTP_LENGTH - i).split("");
      setDigits((prev) => {
        const next = [...prev];
        chars.forEach((c, k) => (next[i + k] = c));
        return next;
      });
      otpRefs.current[Math.min(i + chars.length, OTP_LENGTH - 1)]?.focus();
    }
  };

  const handleDigitKeyDown =
    (i: number) => (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Backspace" && !digits[i] && i > 0) {
        otpRefs.current[i - 1]?.focus();
        setDigit(i - 1, "");
      } else if (e.key === "ArrowLeft" && i > 0) {
        otpRefs.current[i - 1]?.focus();
      } else if (e.key === "ArrowRight" && i < OTP_LENGTH - 1) {
        otpRefs.current[i + 1]?.focus();
      }
    };

  const handleEnter = async () => {
    if (!otpId || !otpComplete || entering) return;
    setOtpError(null);
    setEntering(true);
    try {
      const res = await api.authVerify({
        otpId,
        code: otpCode,
        mobile: mobile.trim(),
      });
      storeUserId(res.userId);
      setDone({ isNew: res.isNew });
      // Brief success flash, then land in the dashboard
      setTimeout(() => router.replace("/dashboard"), 900);
    } catch (err) {
      setOtpError(err instanceof Error ? err.message : "Could not verify code");
      setDigits(Array(OTP_LENGTH).fill(""));
      otpRefs.current[0]?.focus();
    } finally {
      setEntering(false);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-ink text-paper">
      <AmbientBackground />

      <AnimatePresence mode="wait" initial={false}>
        {done ? (
          <SuccessCard key="success" isNew={done.isNew} />
        ) : (
          <motion.div
            key="form"
            className="relative mx-auto flex min-h-screen w-full max-w-[440px] flex-col justify-center px-4 py-10 sm:max-w-md sm:px-5"
            initial={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -60, filter: "blur(6px)" }}
            transition={{ duration: 0.5, ease: EASE }}
          >
            <header className="text-center enter" data-delay="1">
              <p className="text-[10px] uppercase tracking-widest text-paper-muted">
                <span aria-hidden className="mr-1.5 inline-block h-1 w-1 translate-y-[-2px] rounded-full bg-accent align-middle" />
                Cor1x · verified trade network
              </p>
              <p className="mt-6 text-[2rem] font-extrabold leading-none tracking-[-0.045em] text-paper sm:text-[2.5rem]">
                Cor1x
              </p>
            </header>

            <div className="mt-10 text-center enter" data-delay="3">
              <h1 className="text-display text-paper">
                Welcome to <span className="text-gradient">Cor1x</span>
              </h1>
              <p className="mt-3 text-sm leading-relaxed text-paper-muted">
                Sign in or create an account with your mobile number.
              </p>
            </div>

            <section className="mt-8 surface space-y-5 p-5 sm:p-6 enter" data-delay="5">
              <FieldWithAction
                label="Mobile number"
                placeholder="Enter mobile number"
                inputMode="numeric"
                maxLength={10}
                autoComplete="tel-national"
                value={mobile}
                onChange={(e) => {
                  const clean = e.target.value.replace(/\D/g, "").slice(0, 10);
                  setMobile(clean);
                  if (mobileError) setMobileError(null);
                }}
                readOnly={!!sentTo}
                error={mobileError ?? undefined}
                action={
                  sentTo ? (
                    <Button variant="inline" onClick={changeMobile} type="button">
                      Change
                    </Button>
                  ) : (
                    <Button
                      variant="inline"
                      onClick={handleSendOtp}
                      loading={sending}
                      disabled={!mobileValid}
                      type="button"
                    >
                      Send OTP
                    </Button>
                  )
                }
              />

              <AnimatePresence>
                {sentTo ? (
                  <motion.div
                    key="otp"
                    className="space-y-5"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.32, ease: EASE }}
                  >
                    <div>
                      <label className="field-label" htmlFor="otp-0">
                        <span>Enter code</span>
                        {devHint ? (
                          <span className="text-[10px] font-medium uppercase tracking-wider text-paper-muted">
                            {devHint}
                          </span>
                        ) : null}
                      </label>
                      <div className="flex gap-1.5">
                        {digits.map((d, i) => (
                          <motion.input
                            key={i}
                            id={i === 0 ? "otp-0" : undefined}
                            ref={(el) => {
                              otpRefs.current[i] = el;
                            }}
                            inputMode="numeric"
                            autoComplete="one-time-code"
                            maxLength={1}
                            value={d}
                            onChange={handleDigitChange(i)}
                            onKeyDown={handleDigitKeyDown(i)}
                            aria-label={`Digit ${i + 1}`}
                            aria-invalid={otpError ? true : undefined}
                            className="field h-11 flex-1 text-center text-base font-semibold tracking-widest"
                            animate={
                              d
                                ? { scale: [1, 1.06, 1], borderColor: "#D3EC4B" }
                                : { scale: 1 }
                            }
                            transition={{ duration: 0.22, ease: EASE }}
                          />
                        ))}
                      </div>
                      {otpError ? (
                        <p role="alert" className="field-error mt-2">
                          {otpError}
                        </p>
                      ) : (
                        <p className="mt-2 text-xs text-paper-muted">
                          Code sent to{" "}
                          <span className="font-medium text-paper">{sentTo}</span>
                        </p>
                      )}
                    </div>

                    <Button
                      onClick={handleEnter}
                      className="w-full"
                      loading={entering}
                      disabled={!otpComplete}
                      type="button"
                    >
                      Enter <ArrowRight className="h-4 w-4" aria-hidden />
                    </Button>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </section>

            <p className="mt-6 flex items-center justify-center gap-1.5 text-[10px] uppercase tracking-widest text-paper-muted enter" data-delay="7">
              <span aria-hidden className="h-1 w-1 rounded-full bg-accent" />
              Encrypted · SOC-2 mindset · never shared
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}

function SuccessCard({ isNew }: { isNew: boolean }) {
  return (
    <div className="relative mx-auto flex min-h-screen max-w-sm items-center justify-center px-5 text-center enter-fade">
      <div className="w-full">
        <div
          className="mx-auto mt-5 inline-flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-fg enter-pop"
          data-delay="3"
          style={{
            boxShadow:
              "0 0 0 6px rgba(211,236,75,0.14), 0 0 32px -4px rgba(211,236,75,0.55), 0 0 48px -6px rgba(139,92,246,0.35)",
          }}
        >
          <CheckCircle2 className="h-6 w-6" aria-hidden strokeWidth={2.5} />
        </div>

        <h1 className="mt-6 text-display text-paper rise" data-delay="6">
          You&apos;re <span className="text-gradient">in.</span>
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-paper-muted rise" data-delay="8">
          {isNew
            ? "New account created. Profile setup coming soon."
            : "Welcome back. Your dashboard is coming soon."}
        </p>
        <p
          className="mt-8 text-[10px] uppercase tracking-widest text-paper-muted/70 rise"
          data-delay="10"
        >
          Redirecting shortly · stay put
        </p>
      </div>
    </div>
  );
}
