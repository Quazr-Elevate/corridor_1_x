"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

/**
 * Splash / landing — orchestrated exactly per the mobile design canvas.
 *
 * Timeline (all delays match the design):
 *   t=0.00s   Two chartreuse orbs start floating; road dashes scrolling
 *   t=6.80s   Star mark ("X") scales in from a stashed position (xToLockup)
 *   t=7.25s   "Corridor One X" wordmark fades up
 *   t=7.30s   Sign up + Log in + trust chip fade up
 *   t=7.40s   Tagline fades up and begins its 3.6s shimmer loop
 *   t=7.50s   Vehicle track slides in from the left (truckIn)
 *   t=7.60s+  Three vehicles (truck, cargo car, cargo plane) run across
 *             the road in a 9s loop with 3s staggered starts
 *
 * On repeat visits inside the same tab we skip the intro (sessionStorage
 * flag) so navigation stays snappy. Click anywhere during the intro also
 * jumps to the end state.
 */
export default function SplashLanding() {
  const [skip, setSkip] = useState(false);

  useEffect(() => {
    // Session-scoped skip: once the user has seen the intro this tab, skip
    // it on subsequent navigations back to /. Disabled via ?intro=1 for
    // designers who want to re-watch it, and via ?intro=0 to force skip.
    try {
      const q = new URLSearchParams(location.search);
      if (q.get("intro") === "1") return;
      if (q.get("intro") === "0") return setSkip(true);
      if (sessionStorage.getItem("cor1x-splash-seen")) setSkip(true);
      else sessionStorage.setItem("cor1x-splash-seen", "1");
    } catch {
      // Private mode / storage disabled — play the intro anyway.
    }
  }, []);

  const onSkip = () => setSkip(true);
  // When skip=true we swap the negative animation-delay for 0 and shorten
  // durations to 0 so everything jumps straight to the end frame.
  const at = (delay: string) =>
    skip
      ? { animationDelay: "0s", animationDuration: "0.01s" }
      : { animationDelay: delay };

  return (
    <main
      className="relative min-h-dvh overflow-hidden bg-ink text-paper safe-x"
      onClick={onSkip}
    >
      {/* Chartreuse pools — orbFloat / orbFloat2 */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-[-40px] top-[80px] h-[220px] w-[220px] rounded-full animate-orb-float"
        style={{
          background:
            "radial-gradient(circle, rgba(196, 216, 46, 0.16), transparent 70%)",
          filter: "blur(10px)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute right-[-50px] top-[150px] h-[240px] w-[240px] rounded-full animate-orb-float-2"
        style={{
          background:
            "radial-gradient(circle, rgba(196, 216, 46, 0.10), transparent 70%)",
          filter: "blur(12px)",
        }}
      />

      {/* Centered stack — matches the design's absolute-inset layout */}
      <div
        className="relative mx-auto flex min-h-dvh w-full max-w-[440px] flex-col items-center justify-center gap-[18px] px-6"
        style={{
          paddingBottom: "200px",
          paddingTop: "max(env(safe-area-inset-top), 24px)",
        }}
      >
        {/* Star + wordmark row */}
        <div className="flex items-center gap-[14px]">
          <div
            className="h-[52px] w-[52px] opacity-0"
            style={{
              animation: `xToLockup 0.7s cubic-bezier(0.3, 0.9, 0.3, 1) both`,
              ...at("6.8s"),
            }}
          >
            <StarMark />
          </div>
          <div
            className="opacity-0"
            style={{
              animation: `fadeUp 0.5s ease both`,
              ...at("7.25s"),
            }}
          >
            <Wordmark />
          </div>
        </div>

        {/* Tagline with shimmering text-gradient */}
        <div
          className="animate-text-pulse bg-clip-text text-[15px] font-bold tracking-[0.02em] text-transparent opacity-0"
          style={{
            backgroundImage:
              "linear-gradient(90deg, #8A9285 0%, #C4D82E 35%, #C4D82E 50%, #C4D82E 65%, #8A9285 100%)",
            backgroundSize: "300% 100%",
            animation:
              "fadeUp 0.5s ease both, textPulse 3.6s ease-in-out infinite",
            ...at("7.4s"),
          }}
        >
          Trade direct. Settle certain.
        </div>

        {/* Vehicle track */}
        <div
          className="relative mt-[14px] h-[70px] w-3/5 max-w-[250px] opacity-0"
          style={{
            animation: `truckIn 0.85s cubic-bezier(0.25, 0.9, 0.3, 1) both`,
            ...at("7.5s"),
          }}
        >
          <VehicleLane
            delay={skip ? "0s" : "7.6s"}
            duration={skip ? "0.01s" : "9s"}
            svg={<Truck />}
          />
          <VehicleLane
            delay={skip ? "0.01s" : "10.6s"}
            duration={skip ? "0.01s" : "9s"}
            svg={<CargoCar />}
          />
          <VehicleLane
            delay={skip ? "0.02s" : "13.6s"}
            duration={skip ? "0.01s" : "9s"}
            svg={<CargoPlane />}
          />
          {/* Dashed road */}
          <div
            aria-hidden
            className="absolute -left-[12%] -right-[12%] bottom-0 h-[2px] animate-road-move"
            style={{
              background:
                "repeating-linear-gradient(90deg, rgba(196, 216, 46, 0.4) 0px, rgba(196, 216, 46, 0.4) 14px, transparent 14px, transparent 34px)",
            }}
          />
        </div>
      </div>

      {/* Bottom action stack — fades up together */}
      <div
        className="absolute bottom-[36px] left-0 right-0 mx-auto flex w-[76%] max-w-[300px] flex-col gap-[14px] opacity-0"
        style={{
          animation: `fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both`,
          ...at("7.3s"),
          paddingBottom: "env(safe-area-inset-bottom)",
        }}
      >
        <Link
          href="/signup"
          className="flex h-[54px] items-center justify-center rounded-[6px] bg-accent text-[16px] font-semibold text-accent-fg shadow-[0_6px_16px_rgba(0,0,0,0.35)] transition-transform duration-150 active:scale-[0.98]"
        >
          Sign up
        </Link>
        <Link
          href="/login"
          className="flex h-[54px] items-center justify-center rounded-[6px] bg-ink-elevated text-[16px] font-semibold text-paper shadow-[inset_0_0_0_1px_#3A3F38] transition-transform duration-150 active:scale-[0.98]"
        >
          Log in
        </Link>
        <div className="mt-[2px] text-center text-[12px] font-semibold leading-[1.6] text-paper-muted">
          No unverified hands in between.
        </div>
      </div>
    </main>
  );
}

// ── Star mark (4-point) ──────────────────────────────────────────────────────

function StarMark() {
  return (
    <svg
      viewBox="-160 -160 320 320"
      className="h-full w-full"
      aria-hidden
    >
      <path
        d="M 0 -140 C 40 -40 40 -40 140 0 C 40 40 40 40 0 140 C -40 40 -40 40 -140 0 C -40 -40 -40 -40 0 -140 Z"
        fill="#C4D82E"
      />
    </svg>
  );
}

// ── Wordmark ─────────────────────────────────────────────────────────────────
// Design used a raster image at 172px wide. Rendering as text with the same
// visual weight keeps it crisp at any density.
function Wordmark() {
  return (
    <p className="text-[22px] font-semibold tracking-[-0.01em] text-paper">
      Corridor One X
    </p>
  );
}

// ── Vehicle helper — one lane per vehicle, staggered start ───────────────────

function VehicleLane({
  svg,
  delay,
  duration,
}: {
  svg: React.ReactNode;
  delay: string;
  duration: string;
}) {
  return (
    <div
      aria-hidden
      className="absolute inset-0 flex items-end justify-center pb-[6px] opacity-0"
      style={{
        animation: `vehRun ${duration} ease-in-out ${delay} infinite both`,
      }}
    >
      {svg}
    </div>
  );
}

// ── Vehicle SVGs — extracted from the design canvas ──────────────────────────

function Truck() {
  return (
    <svg width="112" height="44" viewBox="0 0 112 44">
      <rect x="2" y="6" width="70" height="26" rx="3" fill="#1E1E1E" stroke="#3A3F38" />
      <rect x="8" y="11" width="58" height="3" rx="1.5" fill="rgba(237,239,234,.12)" />
      <path
        d="M74,12 H92 Q95,12 97,15 L104,24 H108 Q110,24 110,27 V32 Q110,34 108,34 H74 Z"
        fill="#C4D82E"
      />
      <path d="M88,15 H93 L98,23 H88 Z" fill="#0A0A0A" />
      <circle cx="20" cy="36" r="6" fill="#0A0A0A" stroke="#3A3F38" strokeWidth="2" />
      <circle cx="34" cy="36" r="6" fill="#0A0A0A" stroke="#3A3F38" strokeWidth="2" />
      <circle cx="94" cy="36" r="6" fill="#0A0A0A" stroke="#3A3F38" strokeWidth="2" />
    </svg>
  );
}

function CargoCar() {
  return (
    <svg width="120" height="44" viewBox="0 0 120 44">
      <rect x="28" y="12" width="13" height="9" rx="1" fill="#C4D82E" />
      <rect x="43" y="12" width="13" height="9" rx="1" fill="#C4D82E" />
      <rect x="58" y="12" width="13" height="9" rx="1" fill="#8A9285" />
      <rect x="35" y="3" width="13" height="8" rx="1" fill="#8A9285" />
      <rect x="50" y="3" width="13" height="8" rx="1" fill="#C4D82E" />
      <rect x="84" y="4" width="13" height="17" rx="1" fill="#EDEFEA" />
      <rect x="86" y="7" width="9" height="3" rx="1" fill="#0A0A0A" />
      <path d="M6,22 H114 L102,38 H20 Z" fill="#1E1E1E" stroke="#3A3F38" />
      <path d="M6,22 H114 L111,26 H9 Z" fill="#C4D82E" />
    </svg>
  );
}

function CargoPlane() {
  return (
    <svg width="120" height="42" viewBox="0 0 120 42">
      <path d="M92,17 L104,4 H112 L103,17 Z" fill="#C4D82E" />
      <path
        d="M8,24 Q10,18 22,17 H94 Q108,18 114,23 Q108,28 94,29 H22 Q10,28 8,24 Z"
        fill="#EDEFEA"
      />
      <path d="M44,22 L26,36 H38 L58,24 Z" fill="#C4D82E" />
      <circle cx="34" cy="22" r="1.6" fill="#0A0A0A" />
      <circle cx="44" cy="22" r="1.6" fill="#0A0A0A" />
      <circle cx="54" cy="22" r="1.6" fill="#0A0A0A" />
      <circle cx="64" cy="22" r="1.6" fill="#0A0A0A" />
      <circle cx="74" cy="22" r="1.6" fill="#0A0A0A" />
      <path
        d="M10,23 Q13,20 20,19"
        fill="none"
        stroke="#C4D82E"
        strokeWidth="2"
      />
    </svg>
  );
}
