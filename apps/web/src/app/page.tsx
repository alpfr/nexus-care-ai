"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/use-auth";

/**
 * Root route. Pure router: send authenticated users to /dashboard, anyone
 * else to /login. We do this client-side because auth state lives in
 * sessionStorage (not cookies), so the server can't make this decision.
 */
export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    router.replace(isAuthenticated ? "/dashboard" : "/login");
  }, [isAuthenticated, router]);

  return (
    <div className="flex min-h-dvh items-center justify-center text-text-muted">
      <p>Loading…</p>
    </div>
  );
}
