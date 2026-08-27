import type { ReactNode } from "react";
import { ProfileTabs } from "@/components/dashboard/ProfileTabs";

export default function ProfileLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto max-w-2xl">
      <header className="mb-4">
        <p className="text-[10px] uppercase tracking-widest text-paper-muted">
          Profile
        </p>
        <h1 className="mt-2 text-display text-paper">Your profile</h1>
        <p className="mt-2 text-sm text-paper-muted">
          Manage your contact, business identity and payout details.
        </p>
      </header>

      <ProfileTabs />

      <section className="mt-5 surface p-5 sm:p-6">{children}</section>
    </div>
  );
}
