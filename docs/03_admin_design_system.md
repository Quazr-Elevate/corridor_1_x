# Corridor One X — Spatial Admin Design System

Version 1.0 · Foundation · Product: Corridor One X Admin Console

This is the source of truth for the admin console's visual language,
**Corridor Spatial UI**. It is adapted to Cor1x's real brand assets and the
tokens already in the codebase — it is not a generic template.

---

## 1. Philosophy

The admin console is a high-density **operational workspace**, not a
marketing surface. It should read as a calm, precise command center:
spatial surfaces, soft depth, editorial typography, restrained brand lime,
and route-inspired geometry drawn from the Cor1x splash journey.

Rule of thumb: **beautiful because of hierarchy, spacing, typography, and
restraint — never because of effects.**

---

## 2. Brand assets

- **Wordmark:** `public/brand/wordmark.png` (light-on-transparent; render as-is
  on the dark spatial canvas). Do not redraw it.
- **Mark:** `public/brand/x-mark-lime.svg` (woven 4-blade X) for compact
  brand moments, favicons, node accents.
- **Full lockup:** `public/brand/logo.png` (X + wordmark together).

The X geometry, route lines, and nodes are the brand's graphic vocabulary —
use them for progression, connection, and destination motifs.

---

## 3. Typography — Manrope + operational treatment

We keep **Manrope** (the brand font already loaded via `next/font`) rather
than introducing a second family — brand continuity beats novelty, and
Manrope has clean tabular figures for dense data.

The admin gets an operational treatment on top of it:

- **`font-variant-numeric: tabular-nums`** on every metric, count, and table
  figure so numbers align in columns like a real console.
- **`ui-monospace`** (system mono) only for machine values: user IDs, GSTIN,
  PAN, IFSC.

Scale (admin):

| Role        | Size / line-height / weight            |
|-------------|----------------------------------------|
| Page title  | 30px / 1.1 / 600, tracking −0.02em     |
| Metric      | 30px / 1 / 600, tabular-nums           |
| Section     | 15px / 1.4 / 600                        |
| Body        | 13.5px / 1.5 / 400                      |
| Label/meta  | 11px / 1.4 / 600, uppercase, +0.12em   |
| Mono        | 12px ui-monospace                       |

Headings use sentence case. Uppercase is only for micro-labels with letter
spacing — editorial, not bureaucratic.

---

## 4. Color — dark spatial theme

The admin uses its **own** deeper palette, scoped under `.spatial` in
`globals.css`, so it never disturbs the light auth screens or the user
dashboard. Do not derive it by inverting the light theme.

```
Canvas            #090A09
Canvas elevated   #0D0F0D
Surface           #121412   (workspace)
Surface elevated  #171A17   (panels)
Surface interact  #1C201C   (floating controls)
Border            #252A25
Border strong     #303630

Text primary      #F2F4EE
Text secondary    #9AA197
Text tertiary     #6F766E
Text disabled     #50564F

Brand lime        #C4D82E   (the existing Cor1x accent)
Lime fg (on lime) #0A0A0A
```

Lime tints (background washes / states):

```
subtle      rgba(196,216,46,0.06)
interactive rgba(196,216,46,0.10)
hover       rgba(196,216,46,0.14)
focus       rgba(196,216,46,0.18)
```

Semantic (sparingly — never louder than lime):

```
success #A9D84A   warning #E6B84A   error #E56B6F   info #7E9FFF
```

**Accent ratio target: ~85% neutral / ~10% secondary gray / ~5% lime.**
Lime is a signal — active nav, primary action, the funnel bottleneck, a
key number, a focus ring. Never a background, never every border.

---

## 5. Depth — three surfaces, no more

```
Canvas   ──  the page ground (#090A09)
Workspace ── open sections + Surface 01 (#121412)
Elevated  ── panels/controls Surface 02–03 (#171A17 / #1C201C)
```

Depth comes from **tonal contrast + 1px borders + one very soft shadow**,
never heavy shadows, glass, or glow. Max shadow:

```
0 10px 30px rgba(0,0,0,0.35)   (elevated surfaces only)
```

Do **not** wrap every section in a card. Combine open canvas, workspace
surfaces, elevated panels, dividers, and whitespace. Some sections merge
into the page — that openness *is* the spatial aesthetic.

---

## 6. Radius & spacing

Radius: `8 compact · 10 controls · 12 buttons · 16 cards · 20 large`.
Spacing on a 4px base: `4 8 12 16 20 24 32 40 48 64`. Sections breathe at
24–32; page padding 32 (40 on wide).

---

## 7. Components

- **Sidebar (220–240px):** integrated into the canvas, not a black block.
  Active item = subtle lime-tint surface + lime icon, never a bright green
  slab. Brand at top, nav, account at bottom.
- **KPI objects:** icon · metric (dominant, tabular) · label · context.
  Radius 16, padding 20–24, 1px border, whisper shadow. Hover lifts −1px.
- **Verification funnel:** a **progression** (Signed up → Primary → Business
  → Bank → Verified), not five flat bars. Each stage shows count + share;
  lime highlights the **bottleneck** stage.
- **Tables/lists:** compact rows (52–60px), micro uppercase headers,
  horizontal separators only, hover row tint.
- **Status:** small dot + label (`● Verified`), never oversized badges.
  Never state-by-color-alone.
- **Buttons:** primary = lime slab, dark text, 40–44px, radius 12; secondary
  = neutral surface + border; ghost = container on hover only.
- **Inputs:** quiet, 40–44px, radius 10, 1px border, lime border on focus —
  no bright glow ring.

---

## 8. Spatial decoration

Extremely subtle route lines, nodes, X geometry, soft radial lime fields at
**2–8% opacity**, mostly upper-right / behind content. Atmosphere only —
never competing with data. No realistic vehicles, no 3D, no particles.

---

## 9. Motion — subtle, meaningful, 60fps

Motion represents movement / connection / verification / arrival / state
change. Never animate just because you can.

Durations: `120–180ms` small · `200–300ms` medium · `350–500ms` large.
Easing: `cubic-bezier(0.22,1,0.36,1)` (spatial ease-out); ease-in-out for
reversible UI. No bounce.

Patterns:

- **Page/route transition:** `opacity 0→1` + `translateY(8px→0)`, ~300ms.
  Implemented via a `RouteTransition` wrapper keyed on pathname.
- **Section entry:** staggered fadeUp (`rise(n)`), ~80ms apart.
- **Nav active:** smooth tint/indicator transition, ~180ms.
- **Card hover:** `translateY(-1px)` + border/surface tint, ~150ms.
- **Drawer (mobile):** slide-in + backdrop fade.

Animate **only** `transform` and `opacity`. Never width/height/top/left,
never box-shadow, never continuous canvas or backdrop-filter everywhere.
Respect `prefers-reduced-motion` (globals already collapses durations).

---

## 10. Responsive

- **≥1280px:** full sidebar + multi-column.
- **768–1279px:** collapsible sidebar, fewer columns.
- **<768px:** sidebar → drawer; KPIs → 2-col; tables → scroll or card rows.
  Never just shrink the desktop layout.

---

## 11. What it must never become

Generic glassmorphism · neumorphism · cyberpunk · crypto/gaming dashboard ·
sci-fi · card soup · gradient overload · a green dashboard. Lime is a
signal; the console is neutral and calm.

---

## 12. Implementation notes

- Tokens live under `.spatial` in `app/globals.css`; `AdminShell` sets the
  class on its root so all admin routes inherit the theme.
- `RouteTransition` (client) wraps admin page bodies and animates on
  `usePathname()` change.
- Reuse existing `adminApi`, routes, auth, and data. This system is a
  **visual + motion** layer — no business-logic changes.
