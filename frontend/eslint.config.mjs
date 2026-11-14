import nextVitals from "eslint-config-next/core-web-vitals";

const config = [
  ...nextVitals,
  {
    // New with eslint-config-next 16 (React Compiler rules). The code
    // predates them: 55 findings, tracked in CX-144. Warnings until then,
    // so they stay visible without blocking the security upgrade.
    rules: {
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/immutability": "warn",
    },
  },
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
];

export default config;
