"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { LayoutGrid, Plus, Table } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ResidentCard } from "@/components/residents/resident-card";
import { ResidentTable } from "@/components/residents/resident-table";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";

type ViewMode = "cards" | "table";

function detectInitialView(): ViewMode {
  if (typeof window === "undefined") return "cards";
  return window.matchMedia("(min-width: 1024px)").matches ? "table" : "cards";
}

export default function ResidentsPage() {
  const { token, user } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("cards");

  useEffect(() => {
    setMounted(true);
    setViewMode(detectInitialView());
  }, []);

  const { data, isLoading, error } = useQuery({
    queryKey: ["residents", "active"],
    queryFn: ({ signal }) => api.listResidents(token!, "active", signal),
    enabled: mounted && !!token,
  });

  const canAdmit =
    user?.role === "supervisor" || user?.role === "tenant_admin";

  if (!mounted) {
    return <div className="text-text-muted">Loading…</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">Residents</h1>
          <p className="text-sm text-text-muted">
            Active residents in your facility
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div
            role="tablist"
            aria-label="View mode"
            className="inline-flex rounded-md border border-surface-border bg-surface-card p-1"
          >
            <button
              role="tab"
              aria-selected={viewMode === "cards"}
              onClick={() => setViewMode("cards")}
              className={
                "inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium transition " +
                (viewMode === "cards"
                  ? "bg-brand-600 text-text-onbrand"
                  : "text-text-muted hover:text-text-primary")
              }
            >
              <LayoutGrid className="size-4" aria-hidden /> Cards
            </button>
            <button
              role="tab"
              aria-selected={viewMode === "table"}
              onClick={() => setViewMode("table")}
              className={
                "inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium transition " +
                (viewMode === "table"
                  ? "bg-brand-600 text-text-onbrand"
                  : "text-text-muted hover:text-text-primary")
              }
            >
              <Table className="size-4" aria-hidden /> Table
            </button>
          </div>
          {canAdmit ? (
            <Link href="/dashboard/residents/new">
              <Button>
                <Plus className="size-4" aria-hidden /> Admit resident
              </Button>
            </Link>
          ) : null}
        </div>
      </div>

      {isLoading ? (
        <div className="text-text-muted">Loading residents…</div>
      ) : error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-rose-900">
          Could not load residents: {(error as Error).message}
        </div>
      ) : !data || data.length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-border p-10 text-center">
          <p className="text-text-muted">No active residents yet.</p>
          {canAdmit ? (
            <p className="mt-2 text-sm text-text-muted">
              Click <strong>Admit resident</strong> to add the first one.
            </p>
          ) : null}
        </div>
      ) : viewMode === "cards" ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((r) => (
            <ResidentCard key={r.id} resident={r} />
          ))}
        </div>
      ) : (
        <ResidentTable residents={data} />
      )}
    </div>
  );
}
