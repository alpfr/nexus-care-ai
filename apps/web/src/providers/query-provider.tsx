"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

interface QueryProviderProps {
  children: ReactNode;
}

/**
 * TanStack Query provider.
 *
 * One QueryClient per app instance (kept in useState so HMR doesn't recreate
 * it on every render). Defaults are tuned for healthcare workflows: data
 * goes stale fast (clinical info changes minute to minute), retries are
 * limited (we'd rather show a clear error than thrash), and refetch on
 * reconnect is on (handles tablet wifi drops cleanly).
 */
export function QueryProvider({ children }: QueryProviderProps) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000, // 30s — clinical data changes fast
            gcTime: 5 * 60 * 1000, // keep cache 5 min
            retry: 1,
            refetchOnWindowFocus: true,
            refetchOnReconnect: true,
          },
          mutations: {
            retry: 0, // never auto-retry mutations
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
