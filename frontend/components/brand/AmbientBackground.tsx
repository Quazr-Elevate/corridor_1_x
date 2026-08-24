/**
 * AmbientBackground — layered decorative motion behind onboarding pages.
 *
 * Base layer: engineering grid, dot texture, chartreuse + violet drifting orbs,
 * slow scan line, top/bottom vignettes.
 *
 * Commodity layer: 4 SVG floaters (container, rice sprig, cargo stack, ship)
 * drifting on independent slow loops. Very low opacity so they read as
 * ambient world-building — hints of the domain without shouting.
 *
 * Pure CSS/SVG · zero JS · respects prefers-reduced-motion (via globals.css
 * killing animation-duration on the reduce query).
 */
export function AmbientBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      {/* Grid textures */}
      <div className="absolute inset-0 bg-linegrid opacity-70" />
      <div className="absolute inset-0 bg-dotgrid opacity-50" />

      {/* Chartreuse orb — top-left */}
      <div
        className="absolute -left-40 -top-32 h-[420px] w-[420px] rounded-full blur-3xl animate-orb-drift-1 will-change-transform"
        style={{
          background:
            "radial-gradient(closest-side, rgba(211, 236, 75, 0.35), transparent 70%)",
        }}
      />

      {/* Violet orb — bottom-right */}
      <div
        className="absolute -right-40 top-1/3 h-[520px] w-[520px] rounded-full blur-3xl animate-orb-drift-2 will-change-transform"
        style={{
          background:
            "radial-gradient(closest-side, rgba(139, 92, 246, 0.32), transparent 70%)",
        }}
      />

      {/* Centered pulse behind hero */}
      <div
        className="absolute left-1/2 top-24 h-[260px] w-[260px] -translate-x-1/2 rounded-full blur-2xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(211, 236, 75, 0.14), transparent 70%)",
        }}
      />

      {/* Commodity floaters — small SVG glyphs drifting slowly */}
      <CommodityFloaters />

      {/* Scan line sweeping down */}
      <div className="absolute inset-x-0 top-0 h-px opacity-40 animate-scan-line">
        <div
          className="h-full w-full"
          style={{
            background:
              "linear-gradient(to right, transparent, rgba(211, 236, 75, 0.6), rgba(139, 92, 246, 0.4), transparent)",
          }}
        />
      </div>

      {/* Vignettes */}
      <div
        className="absolute inset-x-0 top-0 h-40"
        style={{
          background:
            "linear-gradient(to bottom, rgba(14, 14, 16, 0.85), transparent)",
        }}
      />
      <div
        className="absolute inset-x-0 bottom-0 h-40"
        style={{
          background:
            "linear-gradient(to top, rgba(14, 14, 16, 0.85), transparent)",
        }}
      />
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Commodity floaters — tiny SVG glyphs that drift across the page
// ────────────────────────────────────────────────────────────────

function CommodityFloaters() {
  return (
    <>
      {/* Container ship silhouette — mid-left, slow drift */}
      <div
        className="absolute left-[8%] top-[38%] h-8 w-16 animate-float-slow opacity-[0.09]"
        style={{ animationDelay: "0s" }}
      >
        <ContainerShip />
      </div>

      {/* Cargo container stack — right side, slower drift */}
      <div
        className="absolute right-[10%] top-[62%] h-10 w-10 animate-orb-drift-2 opacity-[0.10]"
        style={{ animationDelay: "-6s" }}
      >
        <CargoStack />
      </div>

      {/* Rice sprig — bottom-left, gentle sway */}
      <div
        className="absolute left-[18%] bottom-[22%] h-14 w-6 animate-float-slow opacity-[0.11]"
        style={{ animationDelay: "-3s" }}
      >
        <RiceSprig />
      </div>

      {/* Compass rose — top-right, slow spin */}
      <div
        className="absolute right-[14%] top-[16%] h-10 w-10 animate-slow-spin opacity-[0.07]"
      >
        <CompassRose />
      </div>

      {/* Trade node dots — thin connecting lines */}
      <svg
        aria-hidden
        className="absolute inset-0 h-full w-full opacity-[0.06]"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="tradeLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#D3EC4B" stopOpacity="0" />
            <stop offset="50%" stopColor="#D3EC4B" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* Two thin diagonal trade routes */}
        <line
          x1="10%"
          y1="30%"
          x2="90%"
          y2="70%"
          stroke="url(#tradeLine)"
          strokeWidth="0.5"
          strokeDasharray="2 6"
        />
        <line
          x1="15%"
          y1="80%"
          x2="88%"
          y2="20%"
          stroke="url(#tradeLine)"
          strokeWidth="0.5"
          strokeDasharray="2 8"
        />
      </svg>
    </>
  );
}

function ContainerShip() {
  return (
    <svg viewBox="0 0 64 32" fill="none" className="h-full w-full">
      <path
        d="M4 22 L60 22 L56 28 L8 28 Z"
        fill="currentColor"
        className="text-paper"
      />
      <rect x="10" y="14" width="8" height="8" fill="currentColor" className="text-accent" />
      <rect x="20" y="12" width="8" height="10" fill="currentColor" className="text-violet" />
      <rect x="30" y="14" width="8" height="8" fill="currentColor" className="text-accent" />
      <rect x="40" y="16" width="6" height="6" fill="currentColor" className="text-violet" />
      <rect x="6" y="17" width="4" height="5" fill="currentColor" className="text-paper-muted" />
    </svg>
  );
}

function CargoStack() {
  return (
    <svg viewBox="0 0 40 40" fill="none" className="h-full w-full">
      <rect x="4" y="20" width="14" height="10" stroke="currentColor" strokeWidth="1" className="text-accent" />
      <rect x="20" y="20" width="14" height="10" stroke="currentColor" strokeWidth="1" className="text-violet" />
      <rect x="12" y="8" width="14" height="10" stroke="currentColor" strokeWidth="1" className="text-paper" />
      <line x1="4" y1="30" x2="34" y2="30" stroke="currentColor" strokeWidth="1" className="text-paper-muted" />
    </svg>
  );
}

function RiceSprig() {
  return (
    <svg viewBox="0 0 24 60" fill="none" className="h-full w-full">
      <path
        d="M12 58 L12 8"
        stroke="currentColor"
        strokeWidth="1"
        className="text-paper"
      />
      {/* Grain clusters */}
      {[10, 18, 26, 34, 42].map((y, i) => (
        <g key={i}>
          <ellipse
            cx={i % 2 === 0 ? 8 : 16}
            cy={y}
            rx="2.5"
            ry="4"
            fill="currentColor"
            className={i % 2 === 0 ? "text-accent" : "text-violet"}
            transform={`rotate(${i % 2 === 0 ? -25 : 25} ${i % 2 === 0 ? 8 : 16} ${y})`}
          />
        </g>
      ))}
      <ellipse cx="12" cy="4" rx="2" ry="3" fill="currentColor" className="text-accent" />
    </svg>
  );
}

function CompassRose() {
  return (
    <svg viewBox="0 0 40 40" fill="none" className="h-full w-full">
      <circle cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="0.5" className="text-paper" />
      <circle cx="20" cy="20" r="12" stroke="currentColor" strokeWidth="0.5" className="text-paper-muted" />
      <path
        d="M20 3 L23 20 L20 37 L17 20 Z"
        fill="currentColor"
        className="text-accent"
      />
      <path
        d="M3 20 L20 23 L37 20 L20 17 Z"
        fill="currentColor"
        className="text-violet"
        opacity="0.7"
      />
      <circle cx="20" cy="20" r="1.5" fill="currentColor" className="text-paper" />
    </svg>
  );
}
