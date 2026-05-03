"use client";

import Link from "next/link";

import { StatusBadge } from "@/components/ui/status-badge";
import type { CodeStatus, ResidentSummary } from "@/lib/api";

const codeStatusLabel: Record<CodeStatus, string> = {
  full: "Full",
  dnr: "DNR",
  dni: "DNI",
  dnr_dni: "DNR/DNI",
  comfort_only: "Comfort",
  unknown: "?",
};

export function ResidentTable({ residents }: { residents: ResidentSummary[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-surface-border bg-surface-card">
      <table className="w-full divide-y divide-surface-border">
        <thead className="bg-surface-muted">
          <tr className="text-left text-xs uppercase tracking-wider text-text-muted">
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Room/Bed</th>
            <th className="px-4 py-3 font-medium">DOB</th>
            <th className="px-4 py-3 font-medium">Admitted</th>
            <th className="px-4 py-3 font-medium">Code</th>
            <th className="px-4 py-3 font-medium">Fall risk</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border">
          {residents.map((r) => (
            <tr
              key={r.id}
              className="text-sm transition hover:bg-surface-muted/40"
            >
              <td className="px-4 py-3">
                <Link
                  href={`/dashboard/residents/${r.id}`}
                  className="font-medium text-text-primary hover:text-brand-700"
                >
                  {r.display_name}
                </Link>
              </td>
              <td className="px-4 py-3 font-mono text-text-muted">
                {r.room ? `${r.room}${r.bed ? `-${r.bed}` : ""}` : "—"}
              </td>
              <td className="px-4 py-3 text-text-muted">
                {new Date(r.date_of_birth).toLocaleDateString()}
              </td>
              <td className="px-4 py-3 text-text-muted">
                {new Date(r.admission_date).toLocaleDateString()}
              </td>
              <td className="px-4 py-3">
                <StatusBadge
                  tone={
                    r.code_status === "unknown"
                      ? "warning"
                      : r.code_status === "full"
                        ? "info"
                        : "neutral"
                  }
                >
                  {codeStatusLabel[r.code_status]}
                </StatusBadge>
              </td>
              <td className="px-4 py-3">
                <StatusBadge
                  tone={
                    r.fall_risk === "high"
                      ? "danger"
                      : r.fall_risk === "moderate"
                        ? "warning"
                        : "neutral"
                  }
                >
                  {r.fall_risk}
                </StatusBadge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
