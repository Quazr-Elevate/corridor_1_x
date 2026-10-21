import type { Metadata, Viewport } from "next";
import { Fragment_Mono } from "next/font/google";
import "./globals.css";
import { ServiceWorkerRegister } from "@/components/pwa/ServiceWorkerRegister";
import { MotionProvider } from "@/components/providers/MotionProvider";

// Fragment Mono — codes, labels, IDs. Switzer (the sans) is served by
// Fontshare, which next/font can't self-host, so it's linked in <head>.
const mono = Fragment_Mono({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Corridor One X — Trade direct. Settle certain.",
  description:
    "Verified commodity trade between India and the Gulf. Verified before contact, masked until escrow, released on delivery.",
  applicationName: "Corridor One X",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    title: "Corridor One X",
    statusBarStyle: "default",
  },
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
    shortcut: ["/icons/icon-192.png"],
  },
  formatDetection: {
    telephone: false,
    email: false,
    address: false,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  viewportFit: "cover",
  themeColor: "#F4F1EC",
  colorScheme: "light",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={mono.variable}>
      <head>
        <link rel="preconnect" href="https://api.fontshare.com" />
        <link rel="preconnect" href="https://cdn.fontshare.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          rel="stylesheet"
          href="https://api.fontshare.com/v2/css?f[]=switzer@400,500,600,700&display=swap"
        />
      </head>
      <body>
        <MotionProvider>{children}</MotionProvider>
        <ServiceWorkerRegister />
      </body>
    </html>
  );
}
