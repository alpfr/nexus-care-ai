"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/hooks/use-auth";
import { api, type CodeStatus, type FallRisk } from "@/lib/api";

const codeStatusLabel: Record<CodeStatus, string> = {
  full: "Full code",
  dnr: "DNR",
  dni: "DNI",
  dnr_dni: "DNR/DNI",
  comfort_only: "Comfort only",
  unknown: "Code status not set",
};

const fallRiskLabel: Record<FallRisk, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  unassessed: "Unassessed",
};

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function ResidentDetailPage({ params }: PageProps) {
  const { id: idStr } = use(params);
  const id = Number(idStr);
  const { token, user } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const residentQuery = useQuery({
    queryKey: ["resident", id],
    queryFn: ({ signal }) => api.getResident(token!, id, signal),
    enabled: mounted && !!token && Number.isFinite(id),
  });

  const ordersQuery = useQuery({
    queryKey: ["resident-orders", id],
    queryFn: ({ signal }) =>
      api.listOrdersForResident(token!, id, "active", signal),
    enabled: mounted && !!token && Number.isFinite(id),
  });

  if (!mounted) {
    return <div className="text-text-muted">Loading…</div>;
  }
  if (residentQuery.isLoading) {
    return <div className="text-text-muted">Loading resident…</div>;
  }
  if (residentQuery.error) {
    return (
      <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-rose-900">
        Could not load resident: {(residentQuery.error as Error).message}
      </div>
    );
  }
  const r = residentQuery.data!;
  const canEdit =
    user?.role === "supervisor" ||
    user?.role === "tenant_admin" ||
    user?.role === "nurse";
  const canPrescribe =
    user?.role === "supervisor" || user?.role === "tenant_admin";

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/residents"
          className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text-primary"
        >
          <ArrowLeft className="size-4" aria-hidden /> All residents
        </Link>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">
            {r.display_name}
          </h1>
          <p className="text-sm text-text-muted">
            {r.legal_first_name} {r.legal_last_name}
            {r.preferred_name ? <> · prefers “{r.preferred_name}”</> : null}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {r.status === "admitted" && canEdit ? (
            <Link href={`/dashboard/residents/${r.id}/edit`}>
              <Button variant="secondary" size="sm">
                <Pencil className="size-4" aria-hidden /> Edit
              </Button>
            </Link>
          ) : null}
        </div>
      </div>

      {r.status !== "admitted" ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-amber-900">
          Resident is <strong>{r.status}</strong>
          {r.discharge_date ? (
            <> as of {new Date(r.discharge_date).toLocaleDateString()}</>
          ) : null}
          . The chart is read-only.
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="space-y-4 lg:col-span-2">
          <div className="rounded-xl border border-surface-border bg-surface-card p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">
              Demographics
            </h2>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-text-muted">Date of birth</dt>
                <dd className="font-medium text-text-primary">
                  {new Date(r.date_of_birth).toLocaleDateString()}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Gender</dt>
                <dd className="font-medium text-text-primary">
                  {r.gender || "—"}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Admitted</dt>
                <dd className="font-medium text-text-primary">
                  {new Date(r.admission_date).toLocaleDateString()}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Room/Bed</dt>
                <dd className="font-mono font-medium text-text-primary">
                  {r.room ? `${r.room}${r.bed ? `-${r.bed}` : ""}` : "—"}
                </dd>
              </div>
            </dl>
          </div>

          <div className="rounded-xl border border-surface-border bg-surface-card p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">
              Clinical
            </h2>
            <div className="mt-3 flex flex-wrap gap-2">
              <StatusBadge
                tone={r.code_status === "unknown" ? "warning" : "info"}
              >
                {codeStatusLabel[r.code_status]}
              </StatusBadge>
              <StatusBadge
                tone={
                  r.fall_risk === "high"
                    ? "danger"
                    : r.fall_risk === "moderate"
                      ? "warning"
                      : "neutral"
                }
              >
                Fall risk: {fallRiskLabel[r.fall_risk]}
              </StatusBadge>
            </div>
            <dl className="mt-4 space-y-3 text-sm">
              <div>
                <dt className="text-text-muted">Allergies</dt>
                <dd className="text-text-primary">
                  {r.allergies_summary || "None documented"}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Dietary restrictions</dt>
                <dd className="text-text-primary">
                  {r.dietary_restrictions || "None"}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Primary physician</dt>
                <dd className="text-text-primary">
                  {r.primary_physician_name || "—"}
                </dd>
              </div>
              {r.chart_note ? (
                <div>
                  <dt className="text-text-muted">Chart note</dt>
                  <dd className="text-text-primary">{r.chart_note}</dd>
                </div>
              ) : null}
            </dl>
          </div>

          <div className="rounded-xl border border-surface-border bg-surface-card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">
                Active medication orders
              </h2>
              {canPrescribe && r.status === "admitted" ? (
                <Link
                  href={`/dashboard/residents/${r.id}/orders/new`}
                  className="text-sm font-medium text-brand-700 hover:underline"
                >
                  Write order
                </Link>
              ) : null}
            </div>
            {ordersQuery.isLoading ? (
              <p className="mt-3 text-sm text-text-muted">Loading orders…</p>
            ) : ordersQuery.error ? (
              <p className="mt-3 text-sm text-rose-700">
                Could not load orders: {(ordersQuery.error as Error).message}
              </p>
            ) : !ordersQuery.data || ordersQuery.data.length === 0 ? (
              <p className="mt-3 text-sm text-text-muted">
                No active medication orders.
              </p>
            ) : (
              <ul className="mt-3 divide-y divide-surface-border">
                {ordersQuery.data.map((o) => (
                  <li key={o.id} className="py-3 text-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-text-primary">
                          {o.medication_display_name}
                        </div>
                        <div className="text-text-muted">
                          {o.dose} · {o.route} · {o.frequency}
                        </div>
                        <div className="text-xs text-text-muted">
                          for {o.indication} · {o.prescriber_name}
                        </div>
                      </div>
                      <div className="shrink-0 space-x-1 text-right">
                        {o.is_prn ? <StatusBadge tone="info">PRN</StatusBadge> : null}
                        {o.witness_required ? (
                          <StatusBadge tone="warning">Witness</StatusBadge>
                        ) : null}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <aside className="space-y-4">
          <div className="rounded-xl border border-surface-border bg-surface-card p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">
              Emergency contact
            </h2>
            <dl className="mt-3 space-y-2 text-sm">
              <div>
                <dt className="text-text-muted">Name</dt>
                <dd className="text-text-primary">
                  {r.emergency_contact_name || "—"}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Relationship</dt>
                <dd className="text-text-primary">
                  {r.emergency_contact_relationship || "—"}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Phone</dt>
                <dd className="font-mono text-text-primary">
                  {r.emergency_contact_phone || "—"}
                </dd>
              </div>
            </dl>
          </div>
        </aside>
      </div>
    </div>
  );
}
