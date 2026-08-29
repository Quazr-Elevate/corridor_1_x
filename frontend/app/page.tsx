"use client";

/* eslint-disable @next/next/no-img-element */
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

/**
 * Splash / landing — full two-phase intro, 1:1 with the design canvas.
 *
 * Phase 1 (0 → 7.25s) — world-map route overlay:
 *   0.05s  dotted world map fades to 55% + latitude arcs appear
 *   0.15s  origin marker (pulsing rings) pops near the right coast
 *   0.65s  chartreuse route draws right→left while a plane flies it
 *   1–2.4s three waypoint dots pop along the route
 *   3.2s   destination X-mark lands, ripple ring at 3.55s
 *   4.0s   camera zooms 3.2× into the destination and the map fades;
 *          the X-mark flies up and scales into a 120px hero (heroIn)
 *   4.7s   wordmark rises under the hero X (brandIn)
 *   5.0s   "Trade direct. Settle certain." rises
 *   5.2s   divider line grows; 5.3–5.6s VERIFIED · DIRECT ·
 *          ESCROW-SECURED badges stagger in
 *   6.8s   whole overlay fades out (splashExit)
 *
 * Phase 2 (6.8s →) — welcome screen:
 *   6.8s   X-mark scales into the lockup (xToLockup)
 *   7.25s  "Corridor One X" wordmark fades up
 *   7.3s   Sign up + Log in + trust chip fade up
 *   7.4s   tagline fades up, starts its 3.6s shimmer
 *   7.5s   vehicle road slides in; truck/cargo/plane loop from 7.6s
 *
 * The intro plays by default on every visit — "/" is the welcome URL the
 * landing page redirects into. ?intro=0 skips (used by in-app back links),
 * and clicking anywhere skips live.
 */
export default function SplashLanding() {
  const router = useRouter();
  const [skip, setSkip] = useState(false);
  // Set when a CTA is tapped: a dark card rises over the splash (the
  // design's cardUp morph), then we navigate underneath it.
  const [exiting, setExiting] = useState<null | "/signup" | "/login">(null);

  const exitTo = (href: "/signup" | "/login") => {
    if (exiting) return;
    setExiting(href);
    router.prefetch(href);
    setTimeout(() => router.push(href), 380);
  };

  useEffect(() => {
    // The intro IS the default — "/" is the welcome URL the landing page
    // redirects to, so every entry gets the full sequence. In-app links
    // that return here (e.g. the auth back button) pass ?intro=0 to skip,
    // and a click anywhere skips live.
    try {
      const q = new URLSearchParams(location.search);
      if (q.get("intro") === "0") setSkip(true);
    } catch {
      // URL parsing failed — just play the intro.
    }
  }, []);

  const onSkip = () => setSkip(true);
  const at = (delay: string) =>
    skip
      ? { animationDelay: "0s", animationDuration: "0.01s" }
      : { animationDelay: delay };

  return (
    <main
      className="relative min-h-dvh overflow-hidden bg-ink text-paper safe-x"
      onClick={onSkip}
    >
      {/* ═══ Phase 1 — world-map route intro (unmounted when skipped) ═══ */}
      {!skip && <IntroOverlay />}

      {/* ═══ Phase 2 — welcome screen ═══ */}
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

      <div
        className="relative mx-auto flex min-h-dvh w-full max-w-[440px] flex-col items-center justify-center gap-[18px] px-6"
        style={{
          paddingBottom: "200px",
          paddingTop: "max(env(safe-area-inset-top), 24px)",
        }}
      >
        <div className="flex items-center gap-[14px]">
          <div
            className="h-[52px] w-[52px] opacity-0"
            style={{
              animation: `xToLockup 0.7s cubic-bezier(0.3, 0.9, 0.3, 1) both`,
              ...at("6.8s"),
            }}
          >
            <img src="/brand/x-mark-lime.svg" alt="" className="h-full w-full" />
          </div>
          <div
            className="opacity-0"
            style={{ animation: `fadeUp 0.5s ease both`, ...at("7.25s") }}
          >
            <img
              src="/brand/wordmark.png"
              alt="Corridor One X"
              className="block w-[172px]"
            />
          </div>
        </div>

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

        <div
          className="relative mt-[14px] h-[70px] w-3/5 max-w-[250px] opacity-0"
          style={{
            animation: `truckIn 0.85s cubic-bezier(0.25, 0.9, 0.3, 1) both`,
            ...at("7.5s"),
          }}
        >
          {/* Vehicles keep their real 9s loops even when the intro is
              skipped — only the initial stagger is compressed so the first
              truck appears immediately instead of 7.6s in. */}
          <VehicleLane delay={skip ? "0s" : "7.6s"} duration="9s" svg={<Truck />} />
          <VehicleLane delay={skip ? "3s" : "10.6s"} duration="9s" svg={<CargoCar />} />
          <VehicleLane delay={skip ? "6s" : "13.6s"} duration="9s" svg={<CargoPlane />} />
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

      <div
        className="absolute bottom-[36px] left-0 right-0 mx-auto flex w-[76%] max-w-[300px] flex-col gap-[14px] opacity-0"
        style={{
          animation: `fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both`,
          ...at("7.3s"),
          paddingBottom: "env(safe-area-inset-bottom)",
        }}
      >
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            exitTo("/signup");
          }}
          className="flex h-[54px] items-center justify-center rounded-[6px] bg-accent text-[16px] font-semibold text-accent-fg shadow-[0_6px_16px_rgba(0,0,0,0.35)] transition-transform duration-150 active:scale-[0.98]"
        >
          Sign up
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            exitTo("/login");
          }}
          className="flex h-[54px] items-center justify-center rounded-[6px] bg-ink-elevated text-[16px] font-semibold text-paper shadow-[inset_0_0_0_1px_#3A3F38] transition-transform duration-150 active:scale-[0.98]"
        >
          Log in
        </button>
        <div className="mt-[2px] text-center text-[12px] font-semibold leading-[1.6] text-paper-muted">
          No unverified hands in between.
        </div>
      </div>

      {/* Exit morph — the design's cardUp: a dark card rises over the
          splash while the route change happens beneath it. The incoming
          auth screen then plays its own fadeUp. */}
      {exiting && (
        <div
          aria-hidden
          className="absolute inset-0 z-20"
          style={{
            background:
              "radial-gradient(100% 50% at 50% -10%, rgba(196, 216, 46, 0.06), transparent 60%), #0A0A0A",
            animation: "cardUp 0.45s cubic-bezier(0.16, 1, 0.3, 1) both",
          }}
        />
      )}
    </main>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Phase 1 — world-map route intro. All geometry/delays verbatim from the
// design canvas (stage is a 340×600 box centered in the viewport).
// ═════════════════════════════════════════════════════════════════════════

function IntroOverlay() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center"
      style={{
        background:
          "radial-gradient(120% 80% at 50% 100%, rgba(196, 216, 46, 0.09), transparent 60%), #0A0A0A",
        animation: "splashExit 0.45s ease 6.8s forwards",
      }}
    >
      <div
        className="absolute left-[-60px] top-[12%] h-[240px] w-[240px] rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(196,216,46,0.07), transparent 70%)",
          animation: "orbFloat 10s ease-in-out infinite",
        }}
      />
      <div
        className="absolute bottom-[10%] right-[-70px] h-[260px] w-[260px] rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(196,216,46,0.05), transparent 70%)",
          animation: "orbFloat2 12s ease-in-out infinite",
        }}
      />

      {/* Stage */}
      <div className="relative h-[600px] w-[340px]">
        {/* Camera group — zooms into the destination at 4s */}
        <div
          className="absolute inset-0"
          style={{
            transformOrigin: "51px 311px",
            animation: "camZoom 0.75s cubic-bezier(0.5, 0.1, 0.3, 1) 4s forwards",
          }}
        >
          {/* Dotted world map */}
          <div
            className="absolute left-0 top-[230px] h-[170px] w-[340px] opacity-0"
            style={{
              background: "url(/brand/world-map.png) center / 340px 170px no-repeat",
              animation: "mapIn 1.2s ease 0.05s forwards",
            }}
          />
          {/* Latitude arcs */}
          <svg
            width="340"
            height="180"
            viewBox="0 0 340 180"
            className="absolute bottom-0 left-0"
            style={{ animation: "dotsIn 0.8s ease 0.05s both" }}
          >
            <path d="M-20,40 Q170,-30 360,40" fill="none" stroke="rgba(196,216,46,.28)" strokeWidth="1.5" strokeDasharray="1.5 9" strokeLinecap="round" />
            <path d="M-20,90 Q170,20 360,90" fill="none" stroke="rgba(196,216,46,.22)" strokeWidth="1.5" strokeDasharray="1.5 11" strokeLinecap="round" />
            <path d="M-20,145 Q170,75 360,145" fill="none" stroke="rgba(237,239,234,.12)" strokeWidth="1.5" strokeDasharray="1.5 13" strokeLinecap="round" />
          </svg>

          {/* Route + plane — this group fades once the camera zoom lands */}
          <div className="absolute inset-0" style={{ animation: "xFade 0.4s ease 4.45s forwards" }}>
            <svg width="340" height="600" viewBox="0 0 340 600" className="absolute inset-0">
              <path
                d="M237,327 Q165,240 96,289"
                fill="none"
                stroke="rgba(196,216,46,.5)"
                strokeWidth="1.5"
                strokeLinecap="round"
                pathLength={1}
                strokeDasharray="1"
                strokeDashoffset="1"
                style={{ animation: "routeTrail 2.9s cubic-bezier(0.5, 0.08, 0.5, 0.92) 0.65s both" }}
              />
            </svg>
            {/* Plane flying the route */}
            <div
              className="absolute left-0 top-0 h-[22px] w-[22px]"
              style={{
                offsetPath: 'path("M 237 327 Q 165 240 88 292")',
                offsetRotate: "auto",
                animation: "flyPath 2.9s cubic-bezier(0.5, 0.08, 0.5, 0.92) 0.65s both",
              }}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" style={{ transform: "rotate(90deg)" }}>
                <path
                  fill="#EDEFEA"
                  d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"
                />
              </svg>
            </div>
          </div>

          {/* Origin glow + marker (right coast) */}
          <div
            className="absolute left-[187px] top-[302px] h-[50px] w-[100px] rounded-full"
            style={{
              background: "radial-gradient(rgba(196,216,46,0.16), transparent 65%)",
              animation: "dotsIn 0.8s ease 0.2s both",
            }}
          />
          <div
            className="absolute left-[221px] top-[311px] h-8 w-8"
            style={{ animation: "dotsIn 0.5s ease 0.15s both" }}
          >
            <div
              className="absolute inset-0 rounded-full border-[1.5px] border-[rgba(196,216,46,0.6)]"
              style={{ animation: "ringPulse 1.8s ease-out 0.3s infinite" }}
            />
            <div
              className="absolute inset-0 rounded-full border border-[rgba(196,216,46,0.4)]"
              style={{ animation: "ringPulse 1.8s ease-out 0.9s infinite" }}
            />
            <div className="absolute left-[11px] top-[11px] h-2.5 w-2.5 rounded-full bg-accent shadow-[0_0_0_3px_rgba(196,216,46,0.25)]" />
          </div>

          {/* Waypoint dots */}
          <div className="absolute left-[199px] top-[290px] h-[5px] w-[5px] rounded-full bg-[rgba(196,216,46,0.8)]" style={{ animation: "nodePop 0.35s ease 1s both" }} />
          <div className="absolute left-[162px] top-[273px] h-[5px] w-[5px] rounded-full bg-[rgba(196,216,46,0.8)]" style={{ animation: "nodePop 0.35s ease 1.65s both" }} />
          <div className="absolute left-[124px] top-[273px] h-[5px] w-[5px] rounded-full bg-[rgba(196,216,46,0.8)]" style={{ animation: "nodePop 0.35s ease 2.35s both" }} />

          {/* Destination X-mark + ripple */}
          <div
            className="absolute left-[73px] top-[277px] h-[30px] w-[30px]"
            style={{ animation: "nodePop 0.45s cubic-bezier(0.16, 1, 0.3, 1) 3.2s both" }}
          >
            <div
              className="absolute -inset-2 rounded-full border border-[rgba(196,216,46,0.4)]"
              style={{ animation: "ringPulse 1.6s ease-out 3.4s infinite" }}
            />
            <div
              className="absolute inset-0"
              style={{ background: "url(/brand/x-mark-lime.svg) center / 30px 30px no-repeat" }}
            />
          </div>
          <div
            className="absolute left-[68px] top-[272px] h-10 w-10 rounded-full border-[1.5px] border-[rgba(196,216,46,0.7)] opacity-0"
            style={{ animation: "destPulse 0.6s ease-out 3.55s forwards" }}
          />
        </div>

        {/* Hero X — flies up out of the zoom into a 120px lockup */}
        <div className="absolute left-[110px] top-[190px] h-[120px] w-[120px]">
          <div
            className="absolute -left-[30px] -top-[30px] h-[180px] w-[180px] rounded-full"
            style={{
              background: "radial-gradient(circle, rgba(196,216,46,0.18), transparent 65%)",
              animation: "glowIn 0.6s ease 4.3s both",
            }}
          />
          <div
            className="absolute -left-[55px] -top-[55px] h-[230px] w-[230px] rounded-full border border-[rgba(196,216,46,0.16)]"
            style={{ animation: "glowIn 0.7s ease 4.4s both" }}
          />
          <div
            className="absolute inset-0"
            style={{
              background: "url(/brand/x-mark-lime.svg) center / 120px 120px no-repeat",
              animation:
                "heroIn 0.75s cubic-bezier(0.5, 0.1, 0.3, 1) 4s both, xFade 0.25s ease 6.75s forwards",
            }}
          />
        </div>

        {/* Wordmark + tagline + divider + badges */}
        <div
          className="absolute left-0 right-0 top-[358px] flex justify-center"
          style={{ animation: "brandIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) 4.7s both" }}
        >
          <img src="/brand/wordmark.png" alt="Corridor One X" className="block w-[216px]" />
        </div>
        <div
          className="absolute left-0 right-0 top-[432px] text-center text-[14.5px] font-semibold leading-[1.6]"
          style={{ animation: "brandIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) 5s both" }}
        >
          <span className="text-paper">Trade direct. </span>
          <span className="text-accent">Settle certain.</span>
        </div>
        <div
          className="absolute left-[110px] right-[110px] top-[482px] h-[1.5px] origin-center rounded-[1px]"
          style={{
            background: "linear-gradient(90deg, transparent, rgba(196,216,46,0.6), transparent)",
            animation: "lineGrow 0.45s cubic-bezier(0.16, 1, 0.3, 1) 5.2s both",
          }}
        />
        <div className="absolute left-0 right-0 top-[498px] flex justify-center gap-[14px] text-[10px] font-extrabold tracking-[0.18em] text-paper-muted">
          <span style={{ animation: "brandIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) 5.3s both" }}>VERIFIED</span>
          <span style={{ animation: "brandIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) 5.42s both" }}>·</span>
          <span style={{ animation: "brandIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) 5.45s both" }}>DIRECT</span>
          <span style={{ animation: "brandIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) 5.57s both" }}>·</span>
          <span style={{ animation: "brandIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) 5.6s both" }}>ESCROW-SECURED</span>
        </div>
      </div>
    </div>
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
      <path d="M10,23 Q13,20 20,19" fill="none" stroke="#C4D82E" strokeWidth="2" />
    </svg>
  );
}
