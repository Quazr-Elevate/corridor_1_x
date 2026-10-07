"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { AuthButton, AuthCard, AuthField, AuthInput, AuthSelect } from "@/components/auth/AuthCard";

const COUNTRIES = [
  "India",
  "United Arab Emirates",
  "Saudi Arabia",
  "Oman",
  "Qatar",
  "Kuwait",
  "Bahrain",
  "United States",
  "United Kingdom",
  "Germany",
  "Netherlands",
  "Singapore",
  "Malaysia",
  "Indonesia",
  "Thailand",
  "Vietnam",
  "Japan",
  "China",
  "South Korea",
  "Australia",
];

/**
 * Signup is email-only. The backend emails a 12-char temp password +
 * a magic-link button; the user either clicks the link (one-click
 * login) or types the password at /login. Either path forces them to
 * set a real password at /dashboard/settings/password before anything
 * else works.
 */
export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [country, setCountry] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<{
    email: string;
    devTempPassword?: string | null;
    devMagicUrl?: string | null;
  } | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (/\d/.test(firstName) || /\d/.test(lastName)) {
      setError("Name should not contain numbers.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await api.signup({
        email: email.trim().toLowerCase(),
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        countryOfResidence: country,
      });
      setSent({
        email: res.email,
        devTempPassword: res.devTempPassword,
        devMagicUrl: res.devMagicUrl,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <AuthCard
        title="Check your inbox"
        subtitle={`We sent your temporary password to ${sent.email}. Open the email, then come back here to log in.`}
        footer={
          <>
            Wrong email?{" "}
            <button
              type="button"
              onClick={() => setSent(null)}
              className="text-accent hover:text-accent-hover underline"
            >
              Start over
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="rounded-field border border-accent/30 bg-accent/10 p-4 text-sm text-paper">
            <div className="font-semibold mb-1">What&apos;s next?</div>
            <ol className="list-decimal pl-5 text-paper-soft space-y-1 text-xs leading-relaxed">
              <li>Open the welcome email we just sent.</li>
              <li>
                Click <strong>Log me in</strong> for one-click entry, OR type
                the temp password on the login page.
              </li>
              <li>You&apos;ll be asked to set a real password of your own.</li>
            </ol>
          </div>

          {(sent.devTempPassword || sent.devMagicUrl) && (
            <div className="rounded-field border border-violet/30 bg-violet/5 p-4 text-xs text-paper">
              <div className="font-semibold mb-2 text-violet">
                Dev shortcut (visible because debug mode is on)
              </div>
              {sent.devTempPassword && (
                <p className="mb-2">
                  Temp password:{" "}
                  <code className="rounded border border-line-soft bg-ink px-1.5 py-0.5 text-accent">
                    {sent.devTempPassword}
                  </code>
                </p>
              )}
              {sent.devMagicUrl && (
                <p>
                  Magic link:{" "}
                  <a
                    href={sent.devMagicUrl}
                    className="text-accent hover:underline break-all"
                  >
                    {sent.devMagicUrl}
                  </a>
                </p>
              )}
            </div>
          )}

          <Link
            href="/login"
            className="block w-full rounded-field bg-accent px-4 py-3 text-center text-sm font-semibold text-accent-fg shadow-cta hover:bg-accent-hover transition"
          >
            Go to login
          </Link>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create your Cor1x account"
      subtitle="India's direct-trade agri marketplace. Use your work email — personal addresses like @gmail.com aren't accepted."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="text-accent hover:text-accent-hover underline">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <AuthField
          label="Work email (required)"
          hint="We'll send your temporary password to this address."
        >
          <AuthInput
            type="email"
            autoComplete="email"
            required
            placeholder="Ex: david.kim@yourcompany.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </AuthField>

        <AuthField label="Name (required)">
          <div className="grid grid-cols-2 gap-3">
            <AuthInput
              type="text"
              autoComplete="given-name"
              required
              minLength={1}
              maxLength={60}
              placeholder="First name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
            />
            <AuthInput
              type="text"
              autoComplete="family-name"
              required
              minLength={1}
              maxLength={60}
              placeholder="Last name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
            />
          </div>
        </AuthField>

        <AuthField label="Country of residence (required)">
          <AuthSelect
            required
            value={country}
            onChange={(e) => setCountry(e.target.value)}
          >
            <option value="" disabled>
              Please select country
            </option>
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </AuthSelect>
        </AuthField>

        {error && (
          <div className="rounded-field border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
            {error}
          </div>
        )}

        <p className="text-xs text-paper-muted text-center">
          By signing up, you agree to our{" "}
          <Link href="/terms" className="text-accent hover:text-accent-hover underline">
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link href="/privacy" className="text-accent hover:text-accent-hover underline">
            Privacy Policy
          </Link>
          .
        </p>

        <AuthButton type="submit" loading={submitting}>
          Sign in
        </AuthButton>
      </form>
    </AuthCard>
  );
}
