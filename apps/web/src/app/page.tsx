"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/use-auth";

/**
 * Root route. Pure router: send authenticated users to /dashboard, anyone
 * else to /login. Auth state lives in sessionStorage (client-only), so we
 * defer the routing decision until after mount to avoid hydration mismatch.
 */
export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted) {
      router.replace(isAuthenticated ? "/dashboard" : "/login");
    }
  }, [mounted, isAuthenticated, router]);

  return (
    <div className="flex min-h-dvh items-center justify-center text-text-muted">
      <p>Loading…</p>
    </div>
  );
}
