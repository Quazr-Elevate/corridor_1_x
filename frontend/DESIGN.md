# Corridor Materials — frontend design rules

Source of truth: the product style guide at
https://portal-web-production-01fd.up.railway.app/styleguide (v0.1).
This file is the short version for anyone writing UI in this repo.

## Surfaces

| Surface | Where | How |
|---|---|---|
| **Cream · trader** | `/dashboard/*`, `/products/*` | `TraderShell` (glass top cluster + bottom dock) |
| **Ink · control tower** | `/admin/*` | `TowerShell` (glass rail on the left, mono status line) |
| **Night** | `/`, `/login`, `/signup`, `/admin/login` | `NightShell` + `NightCard` (night glass over a drawn port scene) |

Every colour class (`bg-surface`, `text-fg-2`, `text-accent`, `bg-amber-soft`, …)
resolves per surface through CSS variables, so components work on both.

## Materials (one effect each)

- **Glass** (`.glass`, `.glass-night`) — *floating controls only*: dock, top cluster,
  menus, sheets, toasts. Never content.
- **Relief** (`.relief`, `.relief-sm`, `Card`) — content you can touch. Raised when
  actionable; **well** (`.well`) is the sunk version for inputs, tracks, quiet panels.
- **Solid** (`.solid`, `SolidPanel`, `Button variant="primary"`) — certain things:
  signed, verified, approved. **Lime lives only here** (`commit` buttons, rail
  current step, progress fill, verified identity).
- **Frost** (`.frost`) — means one thing: the API is masking who this is.

## Colour — scarce on purpose

Ground `#F4F1EC`, ink `#0A0A0A`, ink 70/60% for secondary text. Lime `#C4D82E` is a
fill, never text on cream — use `text-accent` (olive `#55620E`) for lime-as-text.
Amber = *your move*. Danger = rejected / blocked.

## Type — Switzer, Fragment Mono for codes

`t-hero` · `t-large` · `t-title1` · `t-title2` · `t-title3` · `t-headline` · `t-body` ·
`t-callout` · `t-sub` · `t-foot` · `t-label` (mono, uppercase eyebrow) · `t-code` (IDs).

Pattern for a page: `PageHeader` with a mono eyebrow, a large title, a one-line
body subtitle.

## Primitives (`components/ui`)

- `Button` / `LinkButton` / `IconButton` — variants `primary` (solid), `secondary`
  (relief), `commit` (lime), `quiet`, `danger`, `night`, `night-quiet`.
  `IconButton` variants `quiet` · `secondary` · `primary` · `night` (on night
  glass) · `glass` (over photography); sizes `sm` · `md` · `lg`.
  `LinkButton` passes anchor props through (`target`, `rel`, `prefetch`…).
- `buttonClass(variant, size, className)` / `iconButtonClass(…)` — from
  `ui/buttonStyles.ts`, **server-safe**: style a `<Link>` or `<a>` like a button in
  a server component. (`Button.tsx` re-exports `buttonClass` for old imports.)
- `HoldButton` — **hold to commit**; replaces every "are you sure?" for
  irreversible moves (submit for verification, approve, reject, delete).
  `size` `sm` · `md` · `lg` (default, 52px), `block` for full width.
- `Chip` tones `verified` · `move` · `frozen` · `neutral` · `solid` · `quiet`;
  `size` `sm` (tables, dense rows) · `md`. `CountPill`, `CountBadge`.
- `Input` / `Textarea` / `Select` / `ReadField` (wells, mono labels, inline errors;
  `night` prop for night glass).
- `PasswordInput` — `Input` + show/hide toggle (`aria-pressed`); `night` works.
- `Combobox` — searchable single select: `options {value,label,hint?}[]`, `value`,
  `onChange`, `placeholder`, `label`, `allowCustom`, `clearable`, `night`. Glass
  listbox, ↑/↓ · Enter · Esc, flips upward when cramped.
- `Dropzone` — well you drop files into or press to browse: `onFiles`, `accept`,
  `maxBytes`, `multiple`/`maxFiles`, `busy`, `onReject`. Explains refusals inline.
- `RadioCards` — a few big choices as relief cards; the chosen one turns solid
  with a lime icon disc. Real radiogroup (arrows, Home/End). Rows on phones.
- `Segmented` (well track + sliding relief thumb), `ChoiceChips`, `Checkbox`,
  `Progress`, `Rail` (corridor rail: done = solid, current = lime, todo = well).
- `Card`, `SolidPanel`, `PageHeader`, `SectionTitle`, `Notice` (tones `info` ·
  `move` · `frozen` · `verified` · `night`; `className` styles the band,
  `actionClassName` the action), `EmptyState`, `Skeleton`, `Stat`, `CommodityTile`
  (drawn grain until photography lands).
- `ui/Data.tsx` — `KeyValueList` + `KeyValue` (`<dl>`, mono keys; `layout`
  `rows` | `grid`), `StatBlock` (`<dl>` stat; value may be any node, `loading`
  shows a skeleton), `DataTable` (columns `{key, header, cell, align, hideBelow}`;
  scrolls sideways, rows lift on hover, `onRowClick` adds keyboard support,
  `maxHeight` gives a sticky header).
- `Kbd` — mono key cap: `<Kbd>⌘</Kbd><Kbd>K</Kbd>`.
- `Sheet` (glass dialog / bottom sheet), `ToastProvider` + `useToast()`.
- `Icon` — drawn set, 24 grid, 1.5 stroke. Product glyphs: corridor, grain, match,
  relay, vault, passport, radar, shield, lock, pen, sack, ship, plane, truck,
  doc-check, stamp, hold, route, chart… UI glyphs include arrows, chevrons
  (all four), check, plus, close, search, copy, refresh, download, upload,
  calendar, grid, list, sort, file, link, more, external, eye / eye-off.

## Layout tokens

`max-w-page` 1180px (default measure) · `max-w-page-wide` 1320px (tables, market
grids) · screen `3xl` = 1920px for large displays.

## Motion

One curve for everything that arrives: `ease-expo` = `cubic-bezier(0.16, 1, 0.3, 1)`
(`EASE` in `components/motion/tokens.ts`). Springs for things you move (dock,
segmented thumb — `SPRING`). **No scale or rotation on reveals**: opacity and a
short rise only. Reduced Motion removes travel and loops (arrivals keep a short
dissolve); Reduced Transparency makes glass opaque; Increased Contrast hardens
edges — all handled in `globals.css` and by `MotionProvider`.

Components (`components/motion`, client):

- `<Reveal>` — fade + 14px rise once the element enters the viewport (0.7s).
  `as`, `delay`, `y`, `amount`, `once`. `<Reveal as="section" delay={0.1}>…</Reveal>`
- `<Stagger>` + `<StaggerItem>` — reveal children 60ms apart with the same motion.
  `<Stagger as="ul" className="grid …">{rows.map(r => <StaggerItem as="li" …/>)}</Stagger>`
- `<RouteTransition>` — opacity + 8px rise (0.5s) on each navigation. Already
  wired through `app/{dashboard,products,admin}/template.tsx`; shells stay in
  `layout.tsx` so the dock, rail and top cluster never move. Server-rendered
  content is never hidden on first paint.
- `MotionProvider` (`components/providers`) — mounted in `app/layout.tsx`;
  `MotionConfig reducedMotion="user"`.

Reveals start hidden until hydration, so keep the first screen of a server-
rendered page on CSS (`animate-rise`) and use `<Reveal>` below the fold.

CSS helpers (`globals.css`):

- `animate-rise` — the CSS arrival (fade + 10px rise); `animate-fade` — opacity only.
- `animate-drift` / `animate-drift-reverse` — ambient light blobs (26s / 32s).
- `animate-draw` — SVG strokes drawing in; add `pathLength="1"` to the path
  (tune `--draw-duration`, `--draw-delay`).
- `animate-travel` — dashes marching along a live route (`--travel-dash`).
- `animate-beacon` — the ring around a live point. `no-scrollbar` — hide the bar
  on horizontal scrollers.

## Voice

Short, certain, plain. "Your move", "In review", "Verified". Phase-1 matching is
rule-based, so it says **Fit**, never "AI".
