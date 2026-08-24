"use client";

import {
  ChangeEvent,
  ClipboardEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { Button } from "./Button";

const OTP_LENGTH = 6;

interface OtpModalProps {
  open: boolean;
  destination: string;
  /** Dev-mode hint from the backend (e.g. "Use 123456") — shown only when present. */
  devHint?: string;
  onClose: () => void;
  onVerify: (code: string) => Promise<{ ok: boolean; error?: string }>;
  onResend: () => Promise<void>;
}

export function OtpModal({
  open,
  destination,
  devHint,
  onClose,
  onVerify,
  onResend,
}: OtpModalProps) {
  const [digits, setDigits] = useState<string[]>(() => Array(OTP_LENGTH).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resendIn, setResendIn] = useState(30);
  const refs = useRef<Array<HTMLInputElement | null>>([]);

  const code = useMemo(() => digits.join(""), [digits]);
  const complete = code.length === OTP_LENGTH && !digits.includes("");

  useEffect(() => {
    if (!open) return;
    setDigits(Array(OTP_LENGTH).fill(""));
    setError(null);
    setResendIn(30);
    const t = setTimeout(() => refs.current[0]?.focus(), 240);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open || resendIn <= 0) return;
    const iv = setInterval(() => setResendIn((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(iv);
  }, [open, resendIn]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  const setDigit = useCallback((i: number, v: string) => {
    setDigits((prev) => {
      const next = [...prev];
      next[i] = v;
      return next;
    });
  }, []);

  const handleChange = (i: number) => (e: ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, "");
    if (!raw) {
      setDigit(i, "");
      return;
    }
    if (raw.length === 1) {
      setDigit(i, raw);
      if (i < OTP_LENGTH - 1) refs.current[i + 1]?.focus();
    } else {
      const chars = raw.slice(0, OTP_LENGTH - i).split("");
      setDigits((prev) => {
        const next = [...prev];
        chars.forEach((c, k) => (next[i + k] = c));
        return next;
      });
      const target = Math.min(i + chars.length, OTP_LENGTH - 1);
      refs.current[target]?.focus();
    }
  };

  const handleKeyDown = (i: number) => (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !digits[i] && i > 0) {
      refs.current[i - 1]?.focus();
      setDigit(i - 1, "");
    } else if (e.key === "ArrowLeft" && i > 0) {
      refs.current[i - 1]?.focus();
    } else if (e.key === "ArrowRight" && i < OTP_LENGTH - 1) {
      refs.current[i + 1]?.focus();
    }
  };

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, OTP_LENGTH);
    if (!text) return;
    e.preventDefault();
    const chars = text.split("");
    setDigits(() => {
      const next = Array(OTP_LENGTH).fill("");
      chars.forEach((c, k) => (next[k] = c));
      return next;
    });
    const target = Math.min(chars.length, OTP_LENGTH - 1);
    refs.current[target]?.focus();
  };

  const submit = async () => {
    if (!complete || busy) return;
    setBusy(true);
    setError(null);
    const res = await onVerify(code);
    setBusy(false);
    if (!res.ok) {
      setError(res.error || "Incorrect code. Try again.");
      setDigits(Array(OTP_LENGTH).fill(""));
      refs.current[0]?.focus();
    }
  };

  const resend = async () => {
    if (resendIn > 0 || busy) return;
    setBusy(true);
    await onResend();
    setResendIn(30);
    setDigits(Array(OTP_LENGTH).fill(""));
    setError(null);
    refs.current[0]?.focus();
    setBusy(false);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="otp-title"
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-md sm:items-center"
          onClick={onClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <motion.div
            className="relative w-full max-w-sm rounded-t-[20px] border-t border-line-soft bg-ink-soft p-5 shadow-card sm:rounded-card sm:border overflow-hidden"
            onClick={(e) => e.stopPropagation()}
            initial={{ y: 40, opacity: 0, scale: 0.98 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 30, opacity: 0, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 340, damping: 32 }}
          >
            {/* Chartreuse → violet border sheen at the top edge */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 top-0 h-px"
              style={{
                background:
                  "linear-gradient(to right, transparent, rgba(211,236,75,0.7), rgba(139,92,246,0.6), transparent)",
              }}
            />
            <div className="mb-1 flex items-start justify-between">
              <div>
                <h2 id="otp-title" className="text-title text-paper">
                  Verification code
                </h2>
                <p className="mt-1 text-xs text-paper-muted">
                  Sent to{" "}
                  <span className="font-medium text-paper">{destination}</span>
                </p>
              </div>
              <button
                aria-label="Close"
                onClick={onClose}
                className="rounded-full p-1 text-paper-muted transition-colors hover:bg-ink-elevated hover:text-paper"
                type="button"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="mt-5 flex gap-1.5">
              {digits.map((d, i) => (
                <motion.input
                  key={i}
                  ref={(el) => {
                    refs.current[i] = el;
                  }}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={1}
                  value={d}
                  onChange={handleChange(i)}
                  onKeyDown={handleKeyDown(i)}
                  onPaste={i === 0 ? handlePaste : undefined}
                  aria-label={`Digit ${i + 1}`}
                  aria-invalid={error ? true : undefined}
                  className="field h-11 flex-1 text-center text-base font-semibold tracking-widest"
                  animate={
                    d
                      ? { scale: [1, 1.06, 1], borderColor: "#D3EC4B" }
                      : { scale: 1 }
                  }
                  transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                />
              ))}
            </div>

            <AnimatePresence>
              {error && (
                <motion.p
                  className="mt-3 text-sm font-medium text-danger"
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: [0, -6, 6, -3, 3, 0] }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.4 }}
                >
                  {error}
                </motion.p>
              )}
            </AnimatePresence>

            {devHint ? (
              <p className="mt-3 rounded-md border border-dashed border-line bg-ink-elevated/60 px-2.5 py-1.5 text-[11px] text-paper-soft">
                <span className="font-semibold text-accent">Dev mode:</span>{" "}
                {devHint}
              </p>
            ) : null}

            <div className="mt-4 flex items-center justify-between text-xs">
              <button
                type="button"
                onClick={resend}
                disabled={resendIn > 0 || busy}
                className="text-accent underline-offset-4 hover:underline disabled:cursor-not-allowed disabled:text-paper-muted disabled:no-underline"
              >
                {resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code"}
              </button>
              <span className="text-[11px] text-paper-muted">
                Expires in 5 min
              </span>
            </div>

            <Button
              className="mt-4 w-full"
              disabled={!complete}
              loading={busy}
              onClick={submit}
            >
              Verify and continue
            </Button>

            <p className="mt-3 text-center text-[11px] text-paper-muted">
              Didn&apos;t receive it? Check your SMS.
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
