"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import {
  NightCard,
  NightCardFoot,
  NightEyebrow,
  NightShell,
  nightLinkClass,
} from "@/components/shell/NightShell";
import { SignupSteps } from "@/components/auth/SignupSteps";
import { PasswordInput } from "@/components/auth/PasswordInput";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { COUNTRIES } from "@/components/account/countries";
import { Checkbox } from "@/components/ui/Controls";
import { Icon } from "@/components/ui/Icon";
import { Notice } from "@/components/ui/Surface";

const RESEND_COOLDOWN_S = 60;
const CODE_LENGTH = 6;
const PASSWORD_MIN = 8;
const PASSWORD_MAX_BYTES = 72;
const NETWORK_ERROR = "We couldn’t reach the corridor. Check your connection and try again.";

type Step = "email" | "code" | "details";

interface CodeSent {
  email: string;
  resendInSec: number;
  devCode?: string | null;
}

/** Pull "42" out of "Please wait 42s before requesting a new code." */
function waitSeconds(message: string): number | null {
  const m = /(\d+)\s*s\b/.exec(message);
  return m ? Number(m[1]) : null;
}

function accountExists(email: string): ReactNode {
  return (
    <>
      An account with this email already exists.{" "}
      <Link href={`/login?email=${encodeURIComponent(email)}`} className="font-medium underline underline-offset-4">
        Sign in instead
      </Link>
    </>
  );
}

/**
 * Signup is one screen in three steps: work email → 6-digit code from the
 * inbox → name and password. Creating the account signs the trader in.
 */
export default function SignupPage() {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<CodeSent | null>(null);
  const [restartNote, setRestartNote] = useState<ReactNode>(null);

  const current = step === "email" ? 0 : step === "code" ? 1 : 2;

  return (
    <NightShell>
      <NightCard as="main">
        <SignupSteps current={current} />
        {step === "email" ? (
          <EmailStep
            email={email}
            onEmailChange={setEmail}
            note={restartNote}
            onSent={(s) => {
              setRestartNote(null);
              setSent(s);
              setEmail(s.email);
              setStep("code");
            }}
          />
        ) : null}
        {step === "code" && sent ? (
          <CodeStep
            sent={sent}
            onResent={setSent}
            onChangeEmail={() => setStep("email")}
            onVerified={() => setStep("details")}
          />
        ) : null}
        {step === "details" && sent ? (
          <DetailsStep
            email={sent.email}
            onRestart={(note) => {
              setRestartNote(note);
              setSent(null);
              setStep("email");
            }}
          />
        ) : null}
      </NightCard>
    </NightShell>
  );
}

/* ─────────────────────────────── 1 · Email ─────────────────────────────── */

function EmailStep({
  email,
  onEmailChange,
  note,
  onSent,
}: {
  email: string;
  onEmailChange: (v: string) => void;
  note: ReactNode;
  onSent: (s: CodeSent) => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [formError, setFormError] = useState<ReactNode>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setFormError(null);
    const clean = email.trim().toLowerCase();
    if (!clean) {
      setFieldError("Enter your work email.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.signupCode(clean);
      onSent({ email: res.email || clean, resendInSec: res.resendInSec ?? RESEND_COOLDOWN_S, devCode: res.devCode });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) setFormError(accountExists(clean));
        else if (err.status === 400) setFieldError(err.message);
        else if (err.status === 422) setFieldError("Enter a valid email address.");
        else setFormError(err.message);
      } else {
        setFormError(NETWORK_ERROR);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="mt-7 animate-fade">
        <NightEyebrow highlight="India ⇄ UAE">New company</NightEyebrow>
        <h1 className="t-large mt-3 text-cream">
          Bring your company
          <br className="hidden sm:block" /> into the corridor.
        </h1>
        <p className="t-callout mt-3 text-fg-2">We’ll email you a 6-digit code to confirm it’s you.</p>
      </div>

      {note ? (
        <div className="mt-6">
          <Notice tone="move">{note}</Notice>
        </div>
      ) : null}

      <form onSubmit={onSubmit} noValidate className="mt-8 space-y-5">
        <Input
          night
          size="lg"
          label="Work email"
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          autoCapitalize="none"
          spellCheck={false}
          required
          autoFocus
          placeholder="you@company.com"
          hint="Company addresses only. Gmail, Yahoo and similar aren’t accepted."
          error={fieldError}
          value={email}
          onChange={(e) => {
            onEmailChange(e.target.value);
            setFieldError(undefined);
          }}
        />

        {formError ? <Notice tone="frozen">{formError}</Notice> : null}

        <Button type="submit" variant="night" size="lg" block loading={submitting} iconRight="arrow-right">
          Send code
        </Button>
      </form>

      <NightCardFoot>
        Already have an account?{" "}
        <Link href="/login" className={nightLinkClass}>
          Sign in
        </Link>
      </NightCardFoot>
    </>
  );
}

/* ─────────────────────────────── 2 · Code ─────────────────────────────── */

function CodeStep({
  sent,
  onResent,
  onChangeEmail,
  onVerified,
}: {
  sent: CodeSent;
  onResent: (s: CodeSent) => void;
  onChangeEmail: () => void;
  onVerified: () => void;
}) {
  const [code, setCode] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [codeError, setCodeError] = useState<string | undefined>();
  const [cooldown, setCooldown] = useState(sent.resendInSec || RESEND_COOLDOWN_S);
  const [resending, setResending] = useState(false);
  const [status, setStatus] = useState<{ tone: "verified" | "frozen"; text: ReactNode } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const lastTried = useRef<string | null>(null);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = window.setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => window.clearTimeout(t);
  }, [cooldown]);

  async function verify(value: string) {
    if (verifying) return;
    if (value.length !== CODE_LENGTH) {
      setCodeError(`Enter the ${CODE_LENGTH}-digit code from the email.`);
      return;
    }
    lastTried.current = value;
    setCodeError(undefined);
    setStatus(null);
    setVerifying(true);
    try {
      await api.signupVerify(sent.email, value);
      onVerified();
    } catch (err) {
      if (err instanceof ApiError) {
        setCodeError(err.message);
        // Dead codes can't be retried — clear the field so the next one goes in clean.
        if (/expired|too many|request a code|new code/i.test(err.message)) setCode("");
      } else {
        setCodeError(NETWORK_ERROR);
      }
      setVerifying(false);
      inputRef.current?.focus();
    }
  }

  function onCodeChange(raw: string) {
    // Handles typing and pasting ("123 456", "123-456" …) alike.
    const digits = raw.replace(/\D/g, "").slice(0, CODE_LENGTH);
    setCode(digits);
    setCodeError(undefined);
    if (digits.length === CODE_LENGTH && digits !== lastTried.current) void verify(digits);
  }

  async function resend() {
    if (resending || cooldown > 0) return;
    setStatus(null);
    setCodeError(undefined);
    setResending(true);
    try {
      const res = await api.signupCode(sent.email);
      onResent({ email: res.email || sent.email, resendInSec: res.resendInSec, devCode: res.devCode });
      setCooldown(res.resendInSec || RESEND_COOLDOWN_S);
      setCode("");
      lastTried.current = null;
      setStatus({ tone: "verified", text: "New code sent. The previous one no longer works." });
      inputRef.current?.focus();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setStatus({ tone: "frozen", text: accountExists(sent.email) });
      } else if (err instanceof ApiError && err.status === 429) {
        setStatus({ tone: "frozen", text: err.message });
        setCooldown(waitSeconds(err.message) ?? RESEND_COOLDOWN_S);
      } else {
        setStatus({ tone: "frozen", text: err instanceof Error ? err.message : "Couldn’t resend. Try again." });
      }
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="mt-7 animate-fade">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <NightEyebrow highlight="Sent">Confirm your email</NightEyebrow>
          <h1 className="t-large mt-3 text-cream">Check your inbox.</h1>
        </div>
        <span className="grid size-12 shrink-0 place-items-center rounded-full bg-lime-soft text-accent">
          <Icon name="mail" size={22} />
        </span>
      </div>
      <p className="t-callout mt-3 text-fg-2">
        We sent a 6-digit code to <span className="break-all font-medium text-cream">{sent.email}</span>. It
        expires in 10 minutes.
      </p>

      {sent.devCode ? (
        <div className="well mt-6 rounded-[20px] p-4">
          <p className="t-label text-cream/55">Dev shortcut · debug mode</p>
          <p className="t-sub mt-2 text-cream/55">Verification code</p>
          <p className="t-code mt-1 select-all break-all text-[14px] text-accent">{sent.devCode}</p>
        </div>
      ) : null}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void verify(code);
        }}
        noValidate
        className="mt-6 space-y-5"
      >
        <Input
          ref={inputRef}
          night
          size="lg"
          label="Verification code"
          name="code"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]*"
          maxLength={CODE_LENGTH + 4}
          autoFocus
          placeholder="••••••"
          inputClassName="t-code text-center text-[22px] tracking-[0.5em]"
          error={codeError}
          value={code}
          onChange={(e) => onCodeChange(e.target.value)}
          onPaste={(e) => {
            const pasted = e.clipboardData.getData("text");
            if (/\d/.test(pasted)) {
              e.preventDefault();
              onCodeChange(pasted);
            }
          }}
        />

        <Button type="submit" variant="night" size="lg" block loading={verifying} iconRight="arrow-right">
          Verify email
        </Button>
        <Button
          type="button"
          variant="night-quiet"
          size="lg"
          block
          loading={resending}
          disabled={cooldown > 0}
          onClick={resend}
        >
          {cooldown > 0 ? (
            <>
              Resend code in <span className="tabular">{cooldown}s</span>
            </>
          ) : (
            "Resend code"
          )}
        </Button>
      </form>

      <div aria-live="polite" className="mt-4 empty:hidden">
        {status ? <Notice tone={status.tone}>{status.text}</Notice> : null}
      </div>

      <NightCardFoot>
        Wrong email?{" "}
        <button type="button" onClick={onChangeEmail} className={nightLinkClass}>
          Change email
        </button>
      </NightCardFoot>
    </div>
  );
}

/* ─────────────────────────────── 3 · Details ─────────────────────────────── */

type DetailKey = "fullName" | "position" | "country" | "password" | "confirm" | "terms";
type DetailErrors = Partial<Record<DetailKey, string>>;

const COUNTRY_OPTIONS = COUNTRIES.map((c) => ({ value: c.code, label: c.name }));

function DetailsStep({ email, onRestart }: { email: string; onRestart: (note: ReactNode) => void }) {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [position, setPosition] = useState("");
  const [country, setCountry] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [accept, setAccept] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<DetailErrors>({});
  const [formError, setFormError] = useState<ReactNode>(null);

  const clear = (k: DetailKey) =>
    setErrors((fe) => {
      if (!fe[k]) return fe;
      const next = { ...fe };
      delete next[k];
      return next;
    });

  function validate(): DetailErrors {
    const fe: DetailErrors = {};
    if (!fullName.trim()) fe.fullName = "Enter your full name.";
    else if (/\d/.test(fullName)) fe.fullName = "Names can’t contain numbers.";
    if (!country) fe.country = "Pick the home country of your business.";
    if (password.length < PASSWORD_MIN) fe.password = `Use at least ${PASSWORD_MIN} characters.`;
    else if (new TextEncoder().encode(password).length > PASSWORD_MAX_BYTES) fe.password = "That password is too long.";
    if (!fe.password && confirm !== password) fe.confirm = "Passwords don’t match.";
    if (!accept) fe.terms = "Please accept the Terms and Privacy Policy to continue.";
    return fe;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setFormError(null);
    const fe = validate();
    setErrors(fe);
    if (Object.keys(fe).length) return;

    setSubmitting(true);
    try {
      await api.signupComplete({
        email,
        fullName: fullName.trim(),
        position: position.trim() || undefined,
        country,
        password,
        acceptTerms: true,
      });
      router.replace("/dashboard");
      // Keep the button busy until the route changes.
    } catch (err) {
      setSubmitting(false);
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setFormError(accountExists(email));
        } else if (err.status === 400) {
          // Verification missing or expired — the only way forward is a new code.
          onRestart(err.message);
        } else if (err.status === 422) {
          const m = err.message;
          if (/^fullName/i.test(m)) setErrors({ fullName: m.replace(/^fullName:\s*/i, "") });
          else if (/^position/i.test(m)) setErrors({ position: m.replace(/^position:\s*/i, "") });
          else if (/^country/i.test(m)) setErrors({ country: m.replace(/^country:\s*/i, "") });
          else if (/^password/i.test(m)) setErrors({ password: m.replace(/^password:\s*/i, "") });
          else if (/^acceptTerms/i.test(m)) setErrors({ terms: "Please accept the Terms and Privacy Policy to continue." });
          else setFormError(m);
        } else {
          setFormError(err.message);
        }
      } else {
        setFormError(NETWORK_ERROR);
      }
    }
  }

  const termsLink = "rounded-sm text-fg-2 underline decoration-fg/30 underline-offset-4 hover:text-fg";

  return (
    <div className="mt-7 animate-fade">
      <NightEyebrow highlight="Confirmed">Email</NightEyebrow>
      <h1 className="t-large mt-3 text-cream">Set up your account.</h1>
      <p className="t-callout mt-3 text-fg-2">
        Signing up as <span className="break-all font-medium text-cream">{email}</span>.
      </p>

      <form onSubmit={onSubmit} noValidate className="mt-8 space-y-5">
        {/* Lets password managers pair the new password with the email. */}
        <input type="email" name="email" autoComplete="username" value={email} readOnly hidden />

        <Input
          night
          size="lg"
          label="Full name"
          name="fullName"
          autoComplete="name"
          required
          autoFocus
          maxLength={120}
          error={errors.fullName}
          value={fullName}
          onChange={(e) => {
            setFullName(e.target.value);
            clear("fullName");
          }}
        />
        <Input
          night
          size="lg"
          label="Position"
          optional
          name="position"
          autoComplete="organization-title"
          maxLength={120}
          placeholder="e.g. Export manager"
          error={errors.position}
          value={position}
          onChange={(e) => {
            setPosition(e.target.value);
            clear("position");
          }}
        />
        <Select
          night
          size="lg"
          label="Country"
          name="country"
          required
          hint="The home country of your business — drives which KYB documents we'll ask for."
          error={errors.country}
          placeholder="Choose a country"
          value={country}
          options={COUNTRY_OPTIONS}
          onChange={(e) => {
            setCountry(e.target.value);
            clear("country");
          }}
        />
        <PasswordInput
          night
          size="lg"
          label="Password"
          name="password"
          autoComplete="new-password"
          required
          hint={`At least ${PASSWORD_MIN} characters.`}
          error={errors.password}
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            clear("password");
            clear("confirm");
          }}
        />
        <PasswordInput
          night
          size="lg"
          label="Confirm password"
          name="confirmPassword"
          autoComplete="new-password"
          required
          error={errors.confirm}
          value={confirm}
          onChange={(e) => {
            setConfirm(e.target.value);
            clear("confirm");
          }}
        />

        <div>
          <Checkbox
            checked={accept}
            onChange={(v) => {
              setAccept(v);
              clear("terms");
            }}
            label={
              <span className="text-fg-2">
                I agree to the{" "}
                <Link href="/terms" target="_blank" className={termsLink}>
                  Terms
                </Link>{" "}
                and{" "}
                <Link href="/privacy" target="_blank" className={termsLink}>
                  Privacy Policy
                </Link>
                .
              </span>
            }
          />
          {errors.terms ? (
            <p role="alert" className="t-sub mt-2 text-danger">
              {errors.terms}
            </p>
          ) : null}
        </div>

        {formError ? <Notice tone="frozen">{formError}</Notice> : null}

        <Button type="submit" variant="night" size="lg" block loading={submitting} iconRight="arrow-right">
          Create account
        </Button>
      </form>
    </div>
  );
}
