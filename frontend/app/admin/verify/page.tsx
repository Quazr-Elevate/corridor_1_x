"use client";

/**
 * /admin/verify retired — business reviews happen in the Docs lane under
 * the "Business certificate" tab, where profile and cert are reviewed
 * together. Any old bookmark hitting this URL lands on the new surface.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function VerifyRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/admin/docs");
  }, [router]);
  return null;
}
