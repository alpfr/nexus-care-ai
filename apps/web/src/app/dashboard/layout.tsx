"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { LogOut, Pill, Users, LayoutDashboard } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/cn";

interface DashboardLayoutProps {
  children: ReactNode;
}

const navItems = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/residents", label: "Residents", icon: Users, exact: false },
  { href: "/dashboard/medications", label: "Medications", icon: Pill, exact: false },
];

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, user, logout } = useAuth();

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && !isAuthenticated) {
      router.replace("/login");
    }
  }, [mounted, isAuthenticated, router]);

  if (!mounted) {
    return (
      <div
        className="flex min-h-dvh items-center justify-center bg-surface-base"
        suppressHydrationWarning
      >
        <p className="text-text-muted">Loading…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-surface-base">
        <p className="text-text-muted">Redirecting…</p>
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
          <div className="flex items-center gap-6">
            <Logo />
            <nav className="hidden md:flex md:items-center md:gap-1">
              {navItems.map((item) => {
                const active = item.exact
                  ? pathname === item.href
                  : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition",
                      active
                        ? "bg-brand-50 text-brand-700"
                        : "text-text-muted hover:bg-surface-muted hover:text-text-primary",
                    )}
                  >
                    <item.icon className="size-4" aria-hidden />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
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
        <nav className="border-t border-surface-border md:hidden">
          <div className="mx-auto flex max-w-7xl items-center gap-1 overflow-x-auto px-4 py-2 sm:px-6">
            {navItems.map((item) => {
              const active = item.exact
                ? pathname === item.href
                : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "inline-flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium",
                    active
                      ? "bg-brand-50 text-brand-700"
                      : "text-text-muted",
                  )}
                >
                  <item.icon className="size-4" aria-hidden />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
        {children}
      </main>
    </div>
  );
}
