import { redirect } from "next/navigation";

/**
 * Retired. Buyer signup is now the unified /signup page. Old links land
 * here → we bounce to /signup.
 */
export default function BuyerOnboardingRetired() {
  redirect("/signup?intent=buyer");
}
