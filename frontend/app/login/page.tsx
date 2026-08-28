"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth/AuthShell";

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();

  return (
    <AuthShell
      mode="login"
      onAuthed={(_userId, _isNew) => {
        const next = params.get("next") || "/dashboard";
        // router.replace so back button doesn't loop the user through /login.
        router.replace(next);
      }}
    />
  );
}
