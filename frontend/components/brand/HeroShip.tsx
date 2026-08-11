export function HeroShip({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 320 220"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Container ship on water with a stylized world map behind"
    >
      <defs>
        <radialGradient id="globe" cx="60%" cy="45%" r="55%">
          <stop offset="0%" stopColor="#F4F4F5" />
          <stop offset="100%" stopColor="#FFFFFF" />
        </radialGradient>
        <linearGradient id="water" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#E5E7EB" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#E5E7EB" stopOpacity="0" />
        </linearGradient>
        <pattern
          id="dots"
          x="0"
          y="0"
          width="10"
          height="10"
          patternUnits="userSpaceOnUse"
        >
          <circle cx="1" cy="1" r="1" fill="#D4D4D8" />
        </pattern>
      </defs>

      {/* Globe backdrop with dotted texture */}
      <circle cx="205" cy="95" r="82" fill="url(#globe)" />
      <g opacity="0.75">
        {/* Continent-ish clumps rendered as clipped dot fills */}
        <path
          d="M155 70 Q170 55 195 60 Q220 55 240 75 Q255 95 245 115 Q225 130 200 128 Q175 130 160 115 Q150 95 155 70 Z"
          fill="url(#dots)"
        />
        <path
          d="M175 130 Q195 138 220 138 Q235 145 230 158 Q210 168 190 162 Q175 152 175 130 Z"
          fill="url(#dots)"
        />
        <path
          d="M258 88 Q272 90 275 105 Q270 118 258 115 Q252 102 258 88 Z"
          fill="url(#dots)"
        />
      </g>

      {/* Birds */}
      <g fill="none" stroke="#9CA3AF" strokeWidth="1.4" strokeLinecap="round">
        <path d="M120 45 q4 -4 8 0 q4 -4 8 0" />
        <path d="M148 62 q3 -3 6 0 q3 -3 6 0" />
        <path d="M92 68 q3 -3 6 0 q3 -3 6 0" />
      </g>

      {/* Ship hull */}
      <g>
        <path d="M40 158 L280 158 L262 182 L58 182 Z" fill="#0A0A0A" />
        {/* Container stacks */}
        <g fill="#1F2937">
          <rect x="70" y="120" width="30" height="38" />
          <rect x="102" y="112" width="28" height="46" />
          <rect x="132" y="118" width="32" height="40" />
          <rect x="166" y="108" width="30" height="50" />
          <rect x="198" y="120" width="28" height="38" />
          <rect x="228" y="126" width="24" height="32" />
        </g>
        {/* Container highlights */}
        <g fill="#374151">
          <rect x="70" y="120" width="30" height="6" />
          <rect x="102" y="112" width="28" height="6" />
          <rect x="132" y="118" width="32" height="6" />
          <rect x="166" y="108" width="30" height="6" />
          <rect x="198" y="120" width="28" height="6" />
          <rect x="228" y="126" width="24" height="6" />
        </g>
        {/* Bridge tower */}
        <rect x="52" y="132" width="18" height="26" fill="#111827" />
        <rect x="52" y="128" width="18" height="4" fill="#0A0A0A" />
        {/* Crane arm */}
        <g stroke="#374151" strokeWidth="2" fill="none">
          <line x1="270" y1="70" x2="270" y2="158" />
          <line x1="270" y1="70" x2="230" y2="90" />
          <line x1="270" y1="82" x2="242" y2="94" />
        </g>
      </g>

      {/* Water */}
      <rect x="0" y="180" width="320" height="40" fill="url(#water)" />
      <g stroke="#9CA3AF" strokeOpacity="0.35" strokeWidth="1" fill="none">
        <path d="M0 194 Q40 190 80 194 T160 194 T240 194 T320 194" />
        <path d="M0 204 Q40 200 80 204 T160 204 T240 204 T320 204" />
      </g>
    </svg>
  );
}
