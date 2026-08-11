import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0A0A0A",
          soft: "#1A1A1A",
        },
        paper: {
          DEFAULT: "#FFFFFF",
          soft: "#FAFAFA",
          muted: "#F4F4F5",
        },
        line: {
          DEFAULT: "#E5E7EB",
          soft: "#EFEFF1",
          strong: "#D4D4D8",
        },
        mute: {
          DEFAULT: "#6B7280",
          soft: "#9CA3AF",
          strong: "#4B5563",
        },
        accent: {
          DEFAULT: "#166534",
          soft: "#DCFCE7",
          ring: "#22C55E",
        },
        danger: {
          DEFAULT: "#B91C1C",
          soft: "#FEE2E2",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      fontSize: {
        "display-lg": ["2.25rem", { lineHeight: "1.05", letterSpacing: "-0.02em", fontWeight: "700" }],
        "display": ["1.75rem", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "700" }],
        "title": ["1.125rem", { lineHeight: "1.3", letterSpacing: "-0.01em", fontWeight: "600" }],
      },
      borderRadius: {
        card: "16px",
        field: "10px",
        pill: "999px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(10,10,10,0.04), 0 8px 24px rgba(10,10,10,0.04)",
        press: "inset 0 1px 0 rgba(255,255,255,0.06)",
        cta: "0 1px 2px rgba(10,10,10,0.20), 0 8px 24px rgba(10,10,10,0.18)",
        "cta-hover": "0 2px 6px rgba(10,10,10,0.25), 0 14px 34px rgba(10,10,10,0.28)",
        focus: "0 0 0 3px rgba(10,10,10,0.12)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      keyframes: {
        sweep: {
          "0%": { transform: "translateX(-120%) skewX(-12deg)", opacity: "0" },
          "20%": { opacity: "1" },
          "100%": { transform: "translateX(220%) skewX(-12deg)", opacity: "0" },
        },
        ripple: {
          "0%": { transform: "scale(0)", opacity: "0.35" },
          "100%": { transform: "scale(2.6)", opacity: "0" },
        },
      },
      animation: {
        sweep: "sweep 900ms cubic-bezier(0.22, 1, 0.36, 1)",
        ripple: "ripple 550ms cubic-bezier(0.22, 1, 0.36, 1) forwards",
      },
    },
  },
  plugins: [],
};

export default config;
