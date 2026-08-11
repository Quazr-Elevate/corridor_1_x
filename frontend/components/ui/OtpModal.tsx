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

export function OtpModal({ open, destination, devHint, onClose, onVerify, onResend }: OtpModalProps) {
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
    const t = setTimeout(() => refs.current[0]?.focus(), 60);
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

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="otp-title"
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 backdrop-blur-sm sm:items-center"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-t-[24px] bg-white p-6 shadow-card sm:rounded-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-1 flex items-start justify-between">
          <div>
            <h2 id="otp-title" className="text-title text-ink">
              Enter verification code
            </h2>
            <p className="mt-1 text-sm text-mute">
              We sent a 6-digit code to <span className="font-medium text-ink">{destination}</span>
            </p>
          </div>
          <button
            aria-label="Close"
            onClick={onClose}
            className="rounded-full p-1.5 text-mute transition-colors hover:bg-paper-muted hover:text-ink"
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 flex gap-2">
          {digits.map((d, i) => (
            <input
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
              className="field h-12 flex-1 text-center text-lg font-semibold tracking-widest"
            />
          ))}
        </div>

        {error ? <p className="mt-3 text-sm font-medium text-danger">{error}</p> : null}

        {devHint ? (
          <p className="mt-3 rounded-md border border-dashed border-line-strong bg-paper-soft px-3 py-2 text-xs text-mute-strong">
            <span className="font-semibold text-ink">Dev mode:</span> {devHint}
          </p>
        ) : null}

        <div className="mt-5 flex items-center justify-between text-sm">
          <button
            type="button"
            onClick={resend}
            disabled={resendIn > 0 || busy}
            className="text-ink underline-offset-4 hover:underline disabled:cursor-not-allowed disabled:text-mute disabled:no-underline"
          >
            {resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code"}
          </button>
          <span className="text-xs text-mute-soft">Code expires in 5 min</span>
        </div>

        <Button
          className="mt-5 w-full"
          disabled={!complete}
          loading={busy}
          onClick={submit}
        >
          Verify and continue
        </Button>

        <p className="mt-4 text-center text-xs text-mute">
          Didn&apos;t receive it? Check your SMS or try email.
        </p>
      </div>
    </div>
  );
}
