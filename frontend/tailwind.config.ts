import type { Config } from "tailwindcss";

// Cor1x design tokens — dark cinematic surface, chartreuse primary, violet
// complementary. Scale tuned tighter for modern SaaS density (Linear/Vercel-esque).
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surfaces cascade — matches the mobile design canvas exactly.
        ink: {
          DEFAULT: "#0A0A0A", // page background — pure near-black
          soft: "#141416", // card / popover
          elevated: "#1E1E1E",
        },
        // Foreground — cool cream (from design)
        paper: {
          DEFAULT: "#EDEFEA",
          soft: "#C9CBC5",
          muted: "#8A9285",
        },
        line: {
          DEFAULT: "#3A3F38",
          soft: "#242724",
          strong: "#4A4F48",
        },
        mute: {
          DEFAULT: "#8A9285",
          soft: "#6A7266",
          strong: "#A8AFA4",
        },
        // Primary accent — chartreuse (from design canvas, C4D82E).
        accent: {
          DEFAULT: "#C4D82E",
          soft: "rgba(196, 216, 46, 0.10)",
          hover: "#D2E640",
          pressed: "#A8BC22",
          fg: "#0A0A0A",
          ring: "rgba(196, 216, 46, 0.35)",
        },
        // Complementary — violet, for gradient partner + secondary accents
        violet: {
          DEFAULT: "#8B5CF6",
          soft: "rgba(139, 92, 246, 0.12)",
          hover: "#9F75FF",
          deep: "#6D28D9",
          glow: "rgba(139, 92, 246, 0.35)",
        },
        danger: {
          DEFAULT: "#EF4B5C",
          soft: "rgba(239, 75, 92, 0.12)",
        },
      },
      fontFamily: {
        sans: [
          "var(--font-sans)",
          "Switzer",
          "Manrope",
          "system-ui",
          "sans-serif",
        ],
      },
      fontSize: {
        // Tightened scale — SaaS density
        "display-lg": [
          "2.25rem",
          { lineHeight: "1.05", letterSpacing: "-0.03em", fontWeight: "500" },
        ],
        display: [
          "1.625rem",
          { lineHeight: "1.1", letterSpacing: "-0.025em", fontWeight: "500" },
        ],
        title: [
          "1rem",
          { lineHeight: "1.3", letterSpacing: "-0.012em", fontWeight: "500" },
        ],
        // Body defaults tuned smaller
        base: ["0.875rem", { lineHeight: "1.5", letterSpacing: "-0.005em" }],
        sm: ["0.8125rem", { lineHeight: "1.45" }],
        xs: ["0.6875rem", { lineHeight: "1.4" }],
      },
      borderRadius: {
        card: "14px",
        field: "9px",
        pill: "999px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.5), 0 20px 40px -12px rgba(0,0,0,0.55)",
        press: "inset 0 1px 0 rgba(255,255,255,0.06)",
        cta: "0 0 0 1px rgba(196,216,46,0.35), 0 10px 28px -8px rgba(196,216,46,0.35), 0 4px 20px -4px rgba(139,92,246,0.25)",
        "cta-hover":
          "0 0 0 1px rgba(196,216,46,0.55), 0 14px 40px -6px rgba(196,216,46,0.45), 0 6px 28px -4px rgba(139,92,246,0.35)",
        focus: "0 0 0 3px rgba(196,216,46,0.35)",
        glow: "0 0 60px rgba(196,216,46,0.28), 0 0 120px rgba(139,92,246,0.18)",
        "violet-glow": "0 0 60px rgba(139,92,246,0.35), 0 0 120px rgba(139,92,246,0.15)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.22, 1, 0.36, 1)",
        spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
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
        pulseGlow: {
          "0%,100%": {
            filter:
              "drop-shadow(0 0 12px rgba(196,216,46,0.55)) drop-shadow(0 0 40px rgba(139,92,246,0.35))",
          },
          "50%": {
            filter:
              "drop-shadow(0 0 24px rgba(196,216,46,0.75)) drop-shadow(0 0 80px rgba(139,92,246,0.5))",
          },
        },
        floatSlow: {
          "0%,100%": { transform: "translate3d(0,0,0)" },
          "50%": { transform: "translate3d(0,-6px,0)" },
        },
        // Ambient orb drift — used by AmbientBackground
        orbDrift1: {
          "0%,100%": { transform: "translate3d(-20%, -10%, 0) scale(1)" },
          "50%": { transform: "translate3d(15%, 10%, 0) scale(1.1)" },
        },
        orbDrift2: {
          "0%,100%": { transform: "translate3d(20%, 15%, 0) scale(1.05)" },
          "50%": { transform: "translate3d(-15%, -10%, 0) scale(0.95)" },
        },
        // Scan line moving down through the grid
        scanLine: {
          "0%": { transform: "translateY(-100%)", opacity: "0" },
          "10%,90%": { opacity: "1" },
          "100%": { transform: "translateY(2000%)", opacity: "0" },
        },
        // Border sheen for cards
        borderSweep: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        // Slow spin for orbital accents
        slowSpin: {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        // Gradient shift for CTAs
        gradientShift: {
          "0%,100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        // ── Splash intro sequence (from design canvas) ──
        orbFloat: {
          "0%,100%": { transform: "translate(0px,0px) scale(1)" },
          "50%": { transform: "translate(14px,-20px) scale(1.08)" },
        },
        orbFloat2: {
          "0%,100%": { transform: "translate(0px,0px) scale(1)" },
          "50%": { transform: "translate(-18px,16px) scale(0.94)" },
        },
        xToLockup: {
          "0%": { opacity: "0", transform: "translate(72px,178px) scale(2.31)" },
          "12%": { opacity: "1" },
          "100%": { opacity: "1", transform: "translate(0px,0px) scale(1)" },
        },
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(18px)" },
          "100%": { opacity: "1", transform: "translateY(0px)" },
        },
        textPulse: {
          "0%,100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        truckIn: {
          "0%": { opacity: "0", transform: "translateX(-260%)" },
          "55%": { opacity: "1" },
          "85%": { transform: "translateX(8px)" },
          "100%": { opacity: "1", transform: "translateX(0px)" },
        },
        vehRun: {
          "0%": { opacity: "0", transform: "translateX(-150%)" },
          "4%": { opacity: "1" },
          "15%": { transform: "translateX(0px)" },
          "22%": { transform: "translateX(0px)" },
          "31%": { opacity: "1" },
          "33%": { opacity: "0", transform: "translateX(150%)" },
          "100%": { opacity: "0", transform: "translateX(150%)" },
        },
        roadMove: {
          "0%": { backgroundPosition: "0px 0px" },
          "100%": { backgroundPosition: "-34px 0px" },
        },
      },
      animation: {
        sweep: "sweep 900ms cubic-bezier(0.22, 1, 0.36, 1)",
        ripple: "ripple 550ms cubic-bezier(0.22, 1, 0.36, 1) forwards",
        "pulse-glow": "pulseGlow 4200ms ease-in-out infinite",
        "float-slow": "floatSlow 6000ms ease-in-out infinite",
        "orb-drift-1": "orbDrift1 18s ease-in-out infinite",
        "orb-drift-2": "orbDrift2 22s ease-in-out infinite",
        "scan-line": "scanLine 8s linear infinite",
        "slow-spin": "slowSpin 40s linear infinite",
        "gradient-shift": "gradientShift 6s ease-in-out infinite",
        // Splash intro — direct from design canvas timings
        "orb-float": "orbFloat 9s ease-in-out infinite",
        "orb-float-2": "orbFloat2 11s ease-in-out infinite",
        "road-move": "roadMove 0.55s linear infinite",
        "text-pulse": "textPulse 3.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
