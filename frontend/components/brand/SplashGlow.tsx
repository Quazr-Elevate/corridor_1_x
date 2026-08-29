/**
 * Splash-style ambient glow — matches the mobile design canvas. Softer and
 * quieter than <AmbientBackground /> (no orbs drifting, no scan line, no
 * commodity floaters). Just a warm chartreuse pool anchored top-left and a
 * faint violet counter-pool bottom-right, plus the engineering grid.
 *
 * Use for entry pages (splash / login / signup) where the form should be
 * the star. AmbientBackground is heavier and belongs on marketing pages.
 */
export function SplashGlow() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      <div className="absolute inset-0 bg-linegrid opacity-30" />

      {/* Warm chartreuse pool — top-left, matches the design's gold glow */}
      <div
        className="absolute -left-24 -top-24 h-[380px] w-[380px] rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(211, 236, 75, 0.22), transparent 70%)",
        }}
      />

      {/* Faint violet counter-pool — bottom-right */}
      <div
        className="absolute -bottom-24 -right-24 h-[380px] w-[380px] rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(139, 92, 246, 0.16), transparent 70%)",
        }}
      />

      {/* Top + bottom vignette so the page edges recede */}
      <div
        className="absolute inset-x-0 top-0 h-32"
        style={{
          background:
            "linear-gradient(to bottom, rgba(14,14,16,0.9), transparent)",
        }}
      />
      <div
        className="absolute inset-x-0 bottom-0 h-32"
        style={{
          background: "linear-gradient(to top, rgba(14,14,16,0.9), transparent)",
        }}
      />
    </div>
  );
}
