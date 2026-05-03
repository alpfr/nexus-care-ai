"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { StatusBadge } from "@/components/ui/status-badge";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";

export default function MedicationsPage() {
  const { token } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [q, setQ] = useState("");

  useEffect(() => {
    setMounted(true);
  }, []);

  const { data, isLoading, error } = useQuery({
    queryKey: ["medications", q],
    queryFn: ({ signal }) =>
      api.listMedications(token!, { include: "active", q: q || undefined }, signal),
    enabled: mounted && !!token,
  });

  if (!mounted) return <div className="text-text-muted">Loading…</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-text-primary">
          Medication formulary
        </h1>
        <p className="text-sm text-text-muted">
          Drugs available for prescribing in your facility.
        </p>
      </div>

      <Input
        placeholder="Search by name…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="max-w-md"
      />

      {isLoading ? (
        <div className="text-text-muted">Loading…</div>
      ) : error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-rose-900">
          Could not load medications: {(error as Error).message}
        </div>
      ) : !data || data.length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-border p-10 text-center text-text-muted">
          No medications match.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-surface-border bg-surface-card">
          <table className="w-full divide-y divide-surface-border">
            <thead className="bg-surface-muted">
              <tr className="text-left text-xs uppercase tracking-wider text-text-muted">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Strength</th>
                <th className="px-4 py-3 font-medium">Form</th>
                <th className="px-4 py-3 font-medium">Schedule</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {data.map((m) => (
                <tr key={m.id} className="text-sm hover:bg-surface-muted/40">
                  <td className="px-4 py-3">
                    <Link
                      href={`/dashboard/medications/${m.id}`}
                      className="font-medium text-text-primary hover:text-brand-700"
                    >
                      {m.name}
                    </Link>
                    {m.brand_name ? (
                      <span className="ml-2 text-text-muted">({m.brand_name})</span>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 font-mono text-text-muted">
                    {m.strength}
                  </td>
                  <td className="px-4 py-3 text-text-muted">{m.form}</td>
                  <td className="px-4 py-3">
                    {m.schedule === "none" ? (
                      <span className="text-text-muted">—</span>
                    ) : (
                      <StatusBadge tone="warning">CII–{m.schedule}</StatusBadge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
