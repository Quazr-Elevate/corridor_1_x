import type { Config } from "tailwindcss";

// Corridor Materials — design language v0.1.
//
// Colour is scarce on purpose. Every semantic colour resolves to a CSS
// variable defined per surface in globals.css:
//   * trader surface (cream) — the default, used by the trader portal
//   * tower surface (ink)    — [data-surface="tower"], used by ops/admin
// so the same class (`bg-surface`, `text-fg-2`, …) renders correctly on
// both. Lime is a FILL only (solid/commit); `text-accent` is the readable
// olive on cream and lime on ink.
const v = (name: string) => `var(--c-${name})`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Large displays: wider page measure from 1920px up.
      screens: {
        "3xl": "1920px",
      },
      colors: {
        ground: v("ground"),
        surface: {
          DEFAULT: v("surface"),
          2: v("surface-2"),
          3: v("surface-3"),
        },
        fg: {
          DEFAULT: v("fg"),
          2: v("fg-2"),
          3: v("fg-3"),
        },
        line: {
          DEFAULT: v("line"),
          2: v("line-2"),
        },
        accent: v("accent"),
        "lime-soft": v("lime-soft"),
        amber: { DEFAULT: v("amber"), soft: v("amber-soft") },
        danger: { DEFAULT: v("danger"), soft: v("danger-soft") },
        // Fixed brand values — identical on every surface.
        lime: { DEFAULT: "#C4D82E", hover: "#D6E85A" },
        ink: "#0A0A0A",
        cream: "#F4F1EC",
        paper: "#FAF8F4",
      },
      fontFamily: {
        sans: [
          "Switzer",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "sans-serif",
        ],
        mono: [
          "var(--font-mono)",
          "Fragment Mono",
          "ui-monospace",
          "SF Mono",
          "Menlo",
          "monospace",
        ],
      },
      borderRadius: {
        card: "28px",
        sheet: "34px",
        control: "14px",
        field: "16px",
      },
      transitionTimingFunction: {
        expo: "cubic-bezier(0.16, 1, 0.3, 1)",
        calm: "cubic-bezier(0.45, 0, 0.55, 1)",
      },
      maxWidth: {
        page: "1180px",
        "page-wide": "1320px",
      },
      keyframes: {
        rise: {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "none" },
        },
        shimmer: {
          from: { transform: "translateX(-100%)" },
          to: { transform: "translateX(250%)" },
        },
      },
      animation: {
        rise: "rise .7s cubic-bezier(0.16, 1, 0.3, 1) both",
        shimmer: "shimmer 2.4s cubic-bezier(0.45, 0, 0.55, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
