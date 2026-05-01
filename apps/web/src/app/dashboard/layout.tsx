"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { useAuth } from "@/hooks/use-auth";

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter();
  const { isAuthenticated, user, logout } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  // While the redirect is in flight we render nothing rather than flash
  // the dashboard chrome to an unauthenticated user.
  if (!isAuthenticated) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-text-muted">
        <p>Redirecting…</p>
      </div>
    );
  }

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  return (
    <div className="flex min-h-dvh flex-col bg-surface-base">
      <header className="border-b border-surface-border bg-surface-card">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <div className="flex items-center gap-3">
            {user ? (
              <div className="hidden text-right text-sm sm:block">
                <div className="font-medium text-text-primary">{user.full_name}</div>
                <div className="text-xs uppercase tracking-wider text-text-muted">
                  {user.role.replaceAll("_", " ")}
                </div>
              </div>
            ) : null}
            <Button variant="secondary" size="sm" onClick={handleLogout}>
              <LogOut className="size-4" aria-hidden />
              <span>Sign out</span>
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
        {children}
      </main>
    </div>
  );
}
