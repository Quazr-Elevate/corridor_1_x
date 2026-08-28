import { redirect } from "next/navigation";

/**
 * Retired. Seller signup is now the unified /signup page — role is derived
 * from adding a product, so there's no "seller onboarding" flow separate
 * from a buyer's. Old links land here → we bounce to /signup.
 */
export default function SellerOnboardingRetired() {
  redirect("/signup?intent=seller");
}
