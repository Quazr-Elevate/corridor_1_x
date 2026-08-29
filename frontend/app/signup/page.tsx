"use client";

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth/AuthShell";

// useSearchParams() must sit under a Suspense boundary for the static
// prerender pass (Next 14 CSR bailout rule) — hence the inner component.
function SignupInner() {
  const router = useRouter();
  const params = useSearchParams();

  return (
    <AuthShell
      mode="signup"
      onAuthed={(_userId, _isNew) => {
        const next = params.get("next") || "/dashboard";
        router.replace(next);
      }}
    />
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupInner />
    </Suspense>
  );
}
