import type { SVGProps } from "react";

/**
 * Icons — drawn for this product (Corridor Materials). One 24px grid,
 * 1.5 stroke, round caps/joins. Product glyphs (corridor, grain, vault…)
 * come straight from the style guide; UI glyphs (arrow, check, plus…)
 * are drawn to the same rules.
 */
const PATHS = {
  // ── Product glyphs ───────────────────────────────────────────
  corridor: (
    <>
      <path d="M2.5 12h16" />
      <circle cx="6" cy="12" r="1.8" />
      <circle cx="12" cy="12" r="1.8" />
      <path d="M17.5 8.5 21 12l-3.5 3.5" />
    </>
  ),
  grain: (
    <>
      <path d="M12 21V9" />
      <path d="M12 15c-3.2-.6-4.6-2.6-4.6-5.6 3 .2 4.6 2.2 4.6 5.6Z" />
      <path d="M12 12c3.2-.6 4.6-2.6 4.6-5.6-3 .2-4.6 2.2-4.6 5.6Z" />
      <path d="M12 18.5c3-.5 4.3-2.2 4.3-4.9-2.8.2-4.3 2-4.3 4.9Z" />
      <path d="M12 9c-1.2-1-1.6-2.4-1.2-4.6 1.6.8 2 2.6 1.2 4.6Z" />
    </>
  ),
  match: (
    <>
      <circle cx="9" cy="12" r="5.5" />
      <circle cx="15" cy="12" r="5.5" />
    </>
  ),
  relay: (
    <>
      <path d="M5 4.75h14A1.75 1.75 0 0 1 20.75 6.5v8A1.75 1.75 0 0 1 19 16.25h-7.5L7 19.75v-3.5H5A1.75 1.75 0 0 1 3.25 14.5v-8A1.75 1.75 0 0 1 5 4.75Z" />
      <path d="M8 10.5h.01M12 10.5h.01M16 10.5h.01" strokeWidth="2.2" />
    </>
  ),
  vault: (
    <>
      <rect x="3.25" y="4" width="17.5" height="15" rx="3" />
      <circle cx="12" cy="11.5" r="4" />
      <path d="M12 9.25v2.25l1.6 1.1M7 19v1.75M17 19v1.75" />
    </>
  ),
  passport: (
    <>
      <rect x="5" y="2.75" width="14" height="18.5" rx="2" />
      <circle cx="12" cy="10" r="3.5" />
      <path d="M8.5 10h7M12 6.5c.9 1 1.3 2.1 1.3 3.5S12.9 12.5 12 13.5M12 6.5c-.9 1-1.3 2.1-1.3 3.5s.4 2.5 1.3 3.5M9 17.25h6" />
    </>
  ),
  radar: (
    <>
      <circle cx="12" cy="12" r="8.75" />
      <circle cx="12" cy="12" r="4.75" />
      <path d="m12 12 6-6" />
      <circle cx="12" cy="12" r=".9" fill="currentColor" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3 19 6v5.5c0 4.3-2.9 7.7-7 9.5-4.1-1.8-7-5.2-7-9.5V6l7-3Z" />
      <path d="m9 12 2.1 2.1L15.2 10" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="10.5" width="14" height="10" rx="2.25" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5M12 14.5v2" />
    </>
  ),
  unlock: (
    <>
      <rect x="5" y="10.5" width="14" height="10" rx="2.25" />
      <path d="M8 10.5V8a4 4 0 0 1 7.7-1.6M12 14.5v2" />
    </>
  ),
  pen: (
    <>
      <path d="M4 20l4.2-1L18.6 8.6a2.1 2.1 0 0 0-3-3L5.2 16 4 20Z" />
      <path d="m13.75 7.5 3 3" />
    </>
  ),
  sack: (
    <>
      <path d="M8.5 3.5h7l-1.25 3h-4.5L8.5 3.5Z" />
      <path d="M9.75 6.5C7 8.5 5 11.5 5 15a5 5 0 0 0 5 5h4a5 5 0 0 0 5-5c0-3.5-2-6.5-4.75-8.5" />
      <path d="M9.5 13.5h5" />
    </>
  ),
  ship: (
    <>
      <path d="M3 14.5h18l-2 5H5l-2-5Z" />
      <path d="M5.5 14.5V10h13v4.5M9 10V6.5h6V10M12 3.5v3" />
    </>
  ),
  truck: (
    <>
      <path d="M2.75 6h11v10h-11zM13.75 9.5h4l3.5 3.75V16h-7.5" />
      <circle cx="7" cy="17.75" r="1.75" />
      <circle cx="17.5" cy="17.75" r="1.75" />
    </>
  ),
  "doc-check": (
    <>
      <path d="M7 3h7l4.25 4.25V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M14 3v4.25h4.25M9.25 14l1.9 1.9 3.6-3.6" />
    </>
  ),
  scale: (
    <>
      <path d="M12 4v16M6 20h12M5.5 7.5h13" />
      <path d="M5.5 7.5 2.75 13.5a2.75 2.75 0 0 0 5.5 0L5.5 7.5ZM18.5 7.5l-2.75 6a2.75 2.75 0 0 0 5.5 0l-2.75-6Z" />
    </>
  ),
  refund: <path d="M9 14 5 10l4-4M5 10h9.5a5 5 0 0 1 0 10H11" />,
  "eye-off": (
    <>
      <path d="m3 3 18 18" />
      <path d="M10.6 6.1c.46-.07.93-.1 1.4-.1 5 0 8.5 4 9.5 6-.5 1-1.6 2.5-3.2 3.9M6.5 7.6C4.6 8.9 3.1 10.6 2.5 12c1 2 4.5 6 9.5 6 1.6 0 3-.4 4.3-1M9.9 10a3 3 0 0 0 4.1 4.1" />
    </>
  ),
  stamp: (
    <>
      <path d="M9.5 3.5h5l-.75 6.5h-3.5L9.5 3.5Z" />
      <path d="M5 13.5c0-1.9 1.6-3.5 3.5-3.5h7c1.9 0 3.5 1.6 3.5 3.5V15H5v-1.5ZM5.5 18.5h13" />
    </>
  ),
  sparkle: (
    <>
      <path d="m11 3.5 1.7 5 5 1.7-5 1.7-1.7 5-1.7-5-5-1.7 5-1.7 1.7-5Z" />
      <path d="m18 15.5.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" />
    </>
  ),
  route: (
    <>
      <circle cx="6" cy="17.5" r="2" />
      <circle cx="18" cy="6.5" r="2" />
      <path d="M6 15.5V10a3.5 3.5 0 0 1 3.5-3.5H16M18 8.5V14a3.5 3.5 0 0 1-3.5 3.5H8" />
    </>
  ),
  chart: <path d="M5 20v-8M10 20V5M15 20v-6M20 20V9M3 20.25h18" />,
  plane: (
    <path d="M21 15.5 13 11V5.5a1 1 0 0 0-2 0V11l-8 4.5V17l8-2.5V19l-2 1.5V22l3-1 3 1v-1.5L13 19v-4.5l8 2.5v-1.5Z" />
  ),
  hold: (
    <>
      <path d="M12 4.5a6 6 0 0 1 6 6v2.5M6 13v-2.5a6 6 0 0 1 3-5.2" />
      <path d="M9 12v-1.5a3 3 0 0 1 6 0V14c0 3-1.3 5-3 6.5M12 10.5V14c0 2-.6 3.6-1.8 4.9M15 17.5c-.3.9-.7 1.7-1.2 2.4M8.5 15.5c-.2 1.3-.7 2.4-1.5 3.3" />
    </>
  ),

  // ── UI glyphs (same grid + stroke) ───────────────────────────
  "arrow-right": <path d="M4.75 12h14.5M13.5 6.25 19.25 12l-5.75 5.75" />,
  "arrow-left": <path d="M19.25 12H4.75M10.5 6.25 4.75 12l5.75 5.75" />,
  "arrow-up-right": <path d="M7 17 17 7M8.5 7H17v8.5" />,
  check: <path d="m4.75 12.5 4.5 4.5 10-10" />,
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  search: (
    <>
      <circle cx="10.75" cy="10.75" r="6" />
      <path d="m15.25 15.25 4.5 4.5" />
    </>
  ),
  bell: (
    <>
      <path d="M6.25 16.5V11a5.75 5.75 0 0 1 11.5 0v5.5l1.5 1.75H4.75l1.5-1.75Z" />
      <path d="M10 20.25a2.1 2.1 0 0 0 4 0" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8.25" r="3.75" />
      <path d="M4.75 20c.8-3.6 3.7-5.75 7.25-5.75s6.45 2.15 7.25 5.75" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8.5" r="3.5" />
      <path d="M2.75 19.5c.7-3.2 3.2-5.1 6.25-5.1s5.55 1.9 6.25 5.1" />
      <path d="M15.5 5.2a3.5 3.5 0 0 1 0 6.6M17.5 14.6c2 .6 3.3 2.3 3.75 4.9" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2.75v2.5M12 18.75v2.5M21.25 12h-2.5M5.25 12h-2.5M18.54 5.46l-1.77 1.77M7.23 16.77l-1.77 1.77M18.54 18.54l-1.77-1.77M7.23 7.23 5.46 5.46" />
    </>
  ),
  logout: (
    <>
      <path d="M14 4.75H6.75a2 2 0 0 0-2 2v10.5a2 2 0 0 0 2 2H14" />
      <path d="M10.5 12h9.75M16.75 8.5 20.25 12l-3.5 3.5" />
    </>
  ),
  upload: (
    <>
      <path d="M12 15.5V4.5M7.5 8.75 12 4.25l4.5 4.5" />
      <path d="M4.75 14.5v3.75a1.5 1.5 0 0 0 1.5 1.5h11.5a1.5 1.5 0 0 0 1.5-1.5V14.5" />
    </>
  ),
  trash: (
    <>
      <path d="M4.75 6.75h14.5M9.5 6.75V4.75h5v2" />
      <path d="M6.5 6.75 7.4 19.3a1 1 0 0 0 1 .95h7.2a1 1 0 0 0 1-.95l.9-12.55" />
    </>
  ),
  eye: (
    <>
      <path d="M2.5 12c1-2 4.5-6 9.5-6s8.5 4 9.5 6c-1 2-4.5 6-9.5 6s-8.5-4-9.5-6Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  mail: (
    <>
      <rect x="3.25" y="5.25" width="17.5" height="13.5" rx="2.25" />
      <path d="m4 7 8 6 8-6" />
    </>
  ),
  phone: (
    <path d="M6.6 3.75h2.2l1.45 4.1-2 1.3a11 11 0 0 0 6.6 6.6l1.3-2 4.1 1.45v2.2a2 2 0 0 1-2.15 2A16.5 16.5 0 0 1 4.6 5.9a2 2 0 0 1 2-2.15Z" />
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="8.75" />
      <path d="M3.25 12h17.5M12 3.25c2.4 2.5 3.6 5.4 3.6 8.75S14.4 18.25 12 20.75M12 3.25C9.6 5.75 8.4 8.65 8.4 12s1.2 6.25 3.6 8.75" />
    </>
  ),
  pin: (
    <>
      <path d="M12 20.75s6.25-5.6 6.25-10.5a6.25 6.25 0 0 0-12.5 0c0 4.9 6.25 10.5 6.25 10.5Z" />
      <circle cx="12" cy="10.25" r="2.25" />
    </>
  ),
  building: (
    <>
      <path d="M4.75 20.25V5.75a1 1 0 0 1 1-1h7.5a1 1 0 0 1 1 1v14.5M14.25 9.25h4a1 1 0 0 1 1 1v10M3.25 20.25h17.5" />
      <path d="M8 8.5h2.5M8 12h2.5M8 15.5h2.5M16.75 13h.01M16.75 16.5h.01" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8.75" />
      <path d="M12 7.25V12l3.25 2" />
    </>
  ),
  alert: (
    <>
      <path d="M10.3 4.1 2.8 17.2A2 2 0 0 0 4.5 20h15a2 2 0 0 0 1.7-2.8L13.7 4.1a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9.5v4M12 16.75h.01" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.75" />
      <path d="M12 11v5.25M12 7.75h.01" />
    </>
  ),
  "chevron-down": <path d="m6.5 9.5 5.5 5.5 5.5-5.5" />,
  "chevron-right": <path d="m9.5 6.5 5.5 5.5-5.5 5.5" />,
  "chevron-left": <path d="m14.5 6.5-5.5 5.5 5.5 5.5" />,
  "chevron-up": <path d="m6.5 14.5 5.5-5.5 5.5 5.5" />,
  more: <path d="M6 12h.01M12 12h.01M18 12h.01" strokeWidth="2.6" />,
  copy: (
    <>
      <rect x="8.75" y="8.75" width="11.5" height="11.5" rx="2.25" />
      <path d="M15.25 8.75V6A2.25 2.25 0 0 0 13 3.75H6A2.25 2.25 0 0 0 3.75 6v7A2.25 2.25 0 0 0 6 15.25h2.75" />
    </>
  ),
  refresh: (
    <>
      <path d="M19.25 12a7.25 7.25 0 1 1-2.2-5.2L19.25 9" />
      <path d="M19.25 4.5V9h-4.5" />
    </>
  ),
  download: (
    <>
      <path d="M12 4.5v11M7.5 11 12 15.5l4.5-4.5" />
      <path d="M4.75 14.5v3.75a1.5 1.5 0 0 0 1.5 1.5h11.5a1.5 1.5 0 0 0 1.5-1.5V14.5" />
    </>
  ),
  calendar: (
    <>
      <rect x="3.75" y="5.25" width="16.5" height="15" rx="2.25" />
      <path d="M3.75 10h16.5M8 3.25v3.5M16 3.25v3.5" />
      <path d="M8 14h.01M12 14h.01M16 14h.01M8 17h.01M12 17h.01" strokeWidth="2.2" />
    </>
  ),
  grid: (
    <>
      <rect x="4" y="4" width="6.5" height="6.5" rx="1.5" />
      <rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5" />
      <rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5" />
      <rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5" />
    </>
  ),
  list: (
    <>
      <path d="M9 7h11M9 12h11M9 17h11" />
      <path d="M4.5 7h.01M4.5 12h.01M4.5 17h.01" strokeWidth="2.2" />
    </>
  ),
  sort: <path d="M8 4.75v14.5M4.75 8 8 4.75 11.25 8M16 19.25V4.75M12.75 16 16 19.25 19.25 16" />,
  file: (
    <>
      <path d="M7 3h7l4.25 4.25V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M14 3v4.25h4.25" />
    </>
  ),
  link: (
    <>
      <path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1" />
      <path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1" />
    </>
  ),
  external: (
    <>
      <path d="M13.5 4.75h5.75v5.75M19.25 4.75 11 13" />
      <path d="M17.25 13.75v4.5a1 1 0 0 1-1 1H5.75a1 1 0 0 1-1-1V7.75a1 1 0 0 1 1-1h4.5" />
    </>
  ),
  menu: <path d="M4.75 7.5h14.5M4.75 12h14.5M4.75 16.5h14.5" />,
  filter: <path d="M4.25 6.25h15.5M7.25 12h9.5M10.25 17.75h3.5" />,
  image: (
    <>
      <rect x="3.25" y="4.75" width="17.5" height="14.5" rx="2.25" />
      <circle cx="9" cy="10" r="1.75" />
      <path d="m20.25 16-4.5-4.5-8.5 7.75" />
    </>
  ),
  key: (
    <>
      <circle cx="8.25" cy="15.75" r="3.75" />
      <path d="m11 13 8.25-8.25M16.25 7.75l2.25 2.25M14 10l1.75 1.75" />
    </>
  ),
  inbox: (
    <>
      <path d="M3.25 13.5 5.5 5.75a1.5 1.5 0 0 1 1.45-1h10.1a1.5 1.5 0 0 1 1.45 1l2.25 7.75v4.75a1.5 1.5 0 0 1-1.5 1.5H4.75a1.5 1.5 0 0 1-1.5-1.5V13.5Z" />
      <path d="M3.25 13.5h5l1.25 2.25h5l1.25-2.25h5" />
    </>
  ),
} as const;

export type IconName = keyof typeof PATHS;

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  size?: number;
  strokeWidth?: number;
  /** Accessible label; omit for decorative icons. */
  label?: string;
}

export function Icon({ name, size = 18, strokeWidth = 1.5, label, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}
