import type { Metadata } from "next";
import { SellerOnboardingClient } from "@/components/seller/SellerOnboardingClient";

export const metadata: Metadata = {
  title: "Seller Onboarding — Cor1x",
  description:
    "Start your seller journey on Cor1x. Verify your GSTIN or PAN to join a verified rice trade network.",
};

export default function SellerOnboardingPage() {
  return <SellerOnboardingClient />;
}
