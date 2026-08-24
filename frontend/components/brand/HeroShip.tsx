"use client";

import { motion } from "framer-motion";

/**
 * The brand mark: a 4-point chartreuse star with an ambient radial glow.
 * Named `HeroShip` for backwards-compat with existing imports; visually
 * this is now the Corridor One X asterisk mark (see landing-page intro).
 */
export function HeroShip({ className }: { className?: string }) {
  return (
    <div className={`relative flex items-center justify-center ${className ?? ""}`}>
      {/* Ambient radial glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-ambient"
      />

      <motion.svg
        viewBox="0 0 120 120"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="Corridor One X"
        className="relative h-full w-full animate-pulse-glow"
        initial={{ opacity: 0, scale: 0.6, rotate: -8 }}
        animate={{ opacity: 1, scale: 1, rotate: 0 }}
        transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
      >
        <defs>
          <linearGradient id="starGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#E7F87A" />
            <stop offset="55%" stopColor="#D3EC4B" />
            <stop offset="100%" stopColor="#A7C930" />
          </linearGradient>
        </defs>
        {/* 4-point star: concave curves between long spikes */}
        <path
          d="M60 6
             C 60 40, 62 54, 114 60
             C 62 66, 60 80, 60 114
             C 60 80, 58 66, 6 60
             C 58 54, 60 40, 60 6 Z"
          fill="url(#starGrad)"
        />
      </motion.svg>
    </div>
  );
}
