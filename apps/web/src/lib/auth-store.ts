"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import type { MeResponse } from "@/lib/api";

/**
 * Auth store.
 *
 * Holds the access token and the current user. Backed by sessionStorage so
 * the session survives a page reload but does NOT survive a tab close. We
 * use sessionStorage rather than localStorage on purpose:
 *
 *   - Bedside tablets are shared. Closing the tab should log the user out.
 *   - localStorage persists indefinitely; sessionStorage is per-tab.
 *   - sessionStorage isn't a perfect mitigation for stolen-device scenarios
 *     (an attacker with the device can still open the tab and use the token
 *     until it expires) — but it's a real improvement over localStorage and
 *     a sensible default until we add SSO + idle timeouts in Q3.
 *
 * The 8-hour JWT TTL on the backend is the second layer of defense: even if
 * the token is exfiltrated, it expires.
 */

interface AuthState {
  token: string | null;
  expiresAt: number | null; // Unix ms
  user: MeResponse | null;

  setSession: (token: string, expiresInSeconds: number) => void;
  setUser: (user: MeResponse) => void;
  clear: () => void;

  /** Returns true if we have a token AND it hasn't expired. */
  isAuthenticated: () => boolean;
}

// Use a noop storage on the server so SSR doesn't blow up.
const isBrowser = typeof window !== "undefined";

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      expiresAt: null,
      user: null,

      setSession: (token, expiresInSeconds) =>
        set({
          token,
          expiresAt: Date.now() + expiresInSeconds * 1000,
        }),

      setUser: (user) => set({ user }),

      clear: () => set({ token: null, expiresAt: null, user: null }),

      isAuthenticated: () => {
        const { token, expiresAt } = get();
        if (!token || !expiresAt) return false;
        return Date.now() < expiresAt;
      },
    }),
    {
      name: "nexus-care-auth",
      storage: createJSONStorage(() =>
        isBrowser ? window.sessionStorage : (undefined as unknown as Storage),
      ),
      // Don't restore non-serializable function values from storage.
      partialize: (state) => ({
        token: state.token,
        expiresAt: state.expiresAt,
        user: state.user,
      }),
    },
  ),
);
