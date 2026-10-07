"use client";

import Link from "next/link";
import type { ReactNode } from "react";

interface AuthCardProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function AuthCard({ title, subtitle, children, footer }: AuthCardProps) {
  return (
    <div className="relative min-h-dvh bg-ink text-paper flex flex-col overflow-hidden">
      {/* Ambient chartreuse + violet orbs — mirrors the landing page */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-[-60px] top-[80px] h-[260px] w-[260px] rounded-full animate-orb-float"
        style={{
          background:
            "radial-gradient(circle, rgba(196, 216, 46, 0.16), transparent 70%)",
          filter: "blur(20px)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute right-[-80px] bottom-[80px] h-[300px] w-[300px] rounded-full animate-orb-float-2"
        style={{
          background:
            "radial-gradient(circle, rgba(139, 92, 246, 0.14), transparent 70%)",
          filter: "blur(22px)",
        }}
      />

      <header className="relative z-10 px-8 py-6">
        <Link
          href="/?intro=0"
          className="inline-flex items-center gap-2 font-semibold tracking-tight"
        >
          <span className="text-accent text-lg leading-none">✦</span>
          <span className="text-paper">Cor1x</span>
        </Link>
      </header>

      <main className="relative z-10 flex-1 flex items-center justify-center px-4 pb-16">
        <div className="w-full max-w-md">
          <div className="rounded-card border border-line-soft bg-ink-soft/80 backdrop-blur-sm p-8 shadow-card">
            <h1 className="text-display text-paper tracking-tight">{title}</h1>
            {subtitle && (
              <p className="mt-2 text-sm text-paper-muted leading-relaxed">{subtitle}</p>
            )}
            <div className="mt-6">{children}</div>
          </div>
          {footer && (
            <div className="mt-6 text-center text-sm text-paper-muted">{footer}</div>
          )}
        </div>
      </main>
    </div>
  );
}

export function AuthField({
  label,
  hint,
  error,
  children,
  labelExtra,
  anchor,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  children: ReactNode;
  // Right-of-label slot — used by the dashboard to drop a "required
  // for verification" badge next to mandated fields without altering
  // auth-flow screens that share this component.
  labelExtra?: ReactNode;
  // Element id used as a deep-link scroll target. The dashboard's
  // VerificationProgress card routes to /dashboard/account#<anchor>.
  anchor?: string;
}) {
  return (
    <label id={anchor} className="block scroll-mt-24">
      <div className="flex items-center mb-2">
        <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-paper-muted">
          {label}
        </span>
        {labelExtra}
      </div>
      {children}
      {error ? (
        <div className="mt-1.5 text-xs text-danger">{error}</div>
      ) : hint ? (
        <div className="mt-1.5 text-xs text-paper-muted/80">{hint}</div>
      ) : null}
    </label>
  );
}

export function AuthInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-field border border-line-soft bg-ink px-4 py-3 text-paper placeholder-mute-soft/60 focus:outline-none focus:border-accent/60 focus:shadow-focus transition ${props.className ?? ""}`}
    />
  );
}

export function AuthSelect(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  // Custom chevron drawn as inline SVG background so the select looks the same
  // across every browser (native carets vary wildly, and `appearance-none`
  // strips them entirely).
  const chevron =
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%238a9285' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E\")";
  return (
    <select
      {...props}
      style={{
        backgroundImage: chevron,
        backgroundRepeat: "no-repeat",
        backgroundPosition: "right 14px center",
        backgroundSize: "16px 16px",
        ...(props.style ?? {}),
      }}
      className={`w-full rounded-field border border-line-soft bg-ink pl-4 pr-11 py-3 text-paper focus:outline-none focus:border-accent/60 focus:shadow-focus transition appearance-none cursor-pointer ${props.className ?? ""}`}
    />
  );
}

export function AuthTextarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-field border border-line-soft bg-ink px-4 py-3 text-paper placeholder-mute-soft/60 focus:outline-none focus:border-accent/60 focus:shadow-focus transition min-h-[96px] resize-y ${props.className ?? ""}`}
    />
  );
}

export function AuthButton({
  loading,
  variant = "primary",
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
  variant?: "primary" | "ghost";
}) {
  const base =
    "w-full inline-flex items-center justify-center gap-2 rounded-field font-semibold py-3 transition disabled:opacity-50 disabled:cursor-not-allowed";
  const primary =
    "bg-accent hover:bg-accent-hover text-accent-fg shadow-cta hover:shadow-cta-hover";
  const ghost =
    "border border-line-soft bg-transparent text-paper hover:border-line hover:bg-ink-soft/60";
  return (
    <button
      {...rest}
      disabled={loading || rest.disabled}
      className={`${base} ${variant === "primary" ? primary : ghost} ${rest.className ?? ""}`}
    >
      {loading ? (
        <>
          <span className="inline-block w-4 h-4 border-2 border-current/40 border-t-current rounded-full animate-spin" />
          <span>Working…</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}
