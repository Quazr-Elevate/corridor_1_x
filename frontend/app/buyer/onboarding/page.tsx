import type { Metadata } from "next";
import { BuyerOnboardingClient } from "@/components/buyer/BuyerOnboardingClient";

export const metadata: Metadata = {
  title: "Buyer Onboarding — Cor1x",
  description:
    "Start your buyer journey on Cor1x. Source verified rice from mills, manufacturers, and traders across India.",
};

export default function BuyerOnboardingPage() {
  return <BuyerOnboardingClient />;
}
