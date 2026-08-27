import type { Metadata } from "next";
import { AuthClient } from "@/components/auth/AuthClient";

export const metadata: Metadata = {
  title: "Sign in — Cor1x",
  description:
    "Sign in or create your Cor1x account with a mobile number and OTP.",
};

export default function HomePage() {
  return <AuthClient />;
}
