import { redirect } from "next/navigation";

// Legacy path — Seller Details moved to the Trust Score section.
export default function SellerDetailsRedirectPage() {
  redirect("/dashboard/trust-score");
}
