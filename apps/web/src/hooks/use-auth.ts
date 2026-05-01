"use client";

import { useCallback } from "react";

import { ApiError, api, type LoginRequest } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";

/**
 * Auth surface for components.
 *
 * Provides login(), logout(), and the current user. Components should not
 * touch the auth store directly — go through this hook so we can change
 * the storage backend (cookies, etc.) later without touching every consumer.
 */
export function useAuth() {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated());
  const setSession = useAuthStore((s) => s.setSession);
  const setUser = useAuthStore((s) => s.setUser);
  const clear = useAuthStore((s) => s.clear);

  const login = useCallback(
    async (credentials: LoginRequest) => {
      // Step 1: trade credentials for a token.
      const session = await api.login(credentials);
      setSession(session.access_token, session.expires_in);

      // Step 2: fetch the user profile so the UI has it.
      try {
        const me = await api.me(session.access_token);
        setUser(me);
        return me;
      } catch (err) {
        // If /me fails right after a successful login, something is very
        // wrong (revocation race, DB issue). Clear and surface the error.
        clear();
        throw err;
      }
    },
    [setSession, setUser, clear],
  );

  const logout = useCallback(() => {
    clear();
  }, [clear]);

  return {
    token,
    user,
    isAuthenticated,
    login,
    logout,
  };
}

export { ApiError };
