import { ReactNode } from "react";

export function FormCard({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-2xl">
      <header className="mb-6">
        {eyebrow ? (
          <p className="text-[10px] uppercase tracking-widest text-paper-muted">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="mt-2 text-display text-paper">{title}</h1>
        {subtitle ? (
          <p className="mt-2 text-sm text-paper-muted">{subtitle}</p>
        ) : null}
      </header>

      <section className="surface p-5 sm:p-6">{children}</section>
    </div>
  );
}
