"use client";

import { SellerDetailsForm } from "@/components/profile/SellerDetailsForm";

export default function TrustScorePage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <p className="text-[10px] uppercase tracking-widest text-paper-muted">
          Trust score
        </p>
        <h1 className="mt-2 text-display text-paper">Boost your trust</h1>
        <p className="mt-2 text-sm text-paper-muted">
          Buyers move faster with sellers whose identity checks out. Adding
          Udyam, Aadhaar and TAN raises your score and shortens diligence.
        </p>
      </header>

      {/* Seller details form */}
      <section className="surface p-5 sm:p-6">
        <div className="mb-5">
          <p className="text-title text-paper">Verify your seller identity</p>
          <p className="mt-1 text-sm text-paper-muted">
            Optional — every field you add unlocks another notch of trust.
          </p>
        </div>
        <SellerDetailsForm />
      </section>
    </div>
  );
}
