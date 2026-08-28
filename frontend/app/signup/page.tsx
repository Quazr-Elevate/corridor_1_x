"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth/AuthShell";

export default function SignupPage() {
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
