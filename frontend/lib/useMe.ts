"use client";

import { createContext, useContext } from "react";
import type { Me } from "./api";

interface MeContextValue {
  me: Me | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export const MeContext = createContext<MeContextValue>({
  me: null,
  loading: true,
  error: null,
  refetch: async () => {},
});

export function useMe(): MeContextValue {
  return useContext(MeContext);
}
