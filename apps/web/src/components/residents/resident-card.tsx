"use client";

import Link from "next/link";

import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@/lib/cn";
import type { CodeStatus, FallRisk, ResidentSummary } from "@/lib/api";

const codeStatusLabel: Record<CodeStatus, string> = {
  full: "Full code",
  dnr: "DNR",
  dni: "DNI",
  dnr_dni: "DNR/DNI",
  comfort_only: "Comfort only",
  unknown: "Code status not set",
};

const codeStatusTone = (cs: CodeStatus): "warning" | "info" | "neutral" =>
  cs === "unknown" ? "warning" : cs === "full" ? "info" : "neutral";

const fallRiskTone = (f: FallRisk): "danger" | "warning" | "neutral" =>
  f === "high" ? "danger" : f === "moderate" ? "warning" : "neutral";

function ageFromDob(dob: string): number {
  const birth = new Date(dob);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const md = today.getMonth() - birth.getMonth();
  if (md < 0 || (md === 0 && today.getDate() < birth.getDate())) age -= 1;
  return age;
}

export function ResidentCard({
  resident,
  className,
}: {
  resident: ResidentSummary;
  className?: string;
}) {
  return (
    <Link
      href={`/dashboard/residents/${resident.id}`}
      className={cn(
        "block rounded-xl border border-surface-border bg-surface-card p-5 shadow-sm",
        "transition hover:border-brand-400 hover:shadow-md",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-lg font-semibold text-text-primary">
            {resident.display_name}
          </h3>
          <p className="text-sm text-text-muted">
            Age {ageFromDob(resident.date_of_birth)} · Admitted{" "}
            {new Date(resident.admission_date).toLocaleDateString()}
          </p>
        </div>
        {resident.room ? (
          <div className="shrink-0 rounded-md bg-surface-muted px-3 py-1 text-center">
            <div className="text-[10px] uppercase tracking-wider text-text-muted">
              Room/Bed
            </div>
            <div className="font-mono text-sm font-medium text-text-primary">
              {resident.room}
              {resident.bed ? `-${resident.bed}` : ""}
            </div>
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <StatusBadge tone={codeStatusTone(resident.code_status)}>
          {codeStatusLabel[resident.code_status]}
        </StatusBadge>
        {resident.fall_risk !== "low" && resident.fall_risk !== "unassessed" ? (
          <StatusBadge tone={fallRiskTone(resident.fall_risk)}>
            Fall risk: {resident.fall_risk}
          </StatusBadge>
        ) : null}
        {resident.fall_risk === "unassessed" ? (
          <StatusBadge tone="neutral">Fall risk unassessed</StatusBadge>
        ) : null}
      </div>
    </Link>
  );
}
