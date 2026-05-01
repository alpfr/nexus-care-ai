"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Building2, ShieldCheck, UserRound } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

export default function DashboardPage() {
  const { token, user } = useAuth();

  // Live-fetch /api/me on dashboard mount. This serves two purposes:
  //   1. Confirms the token still works (revoked tokens get bounced here).
  //   2. Surfaces tenant state changes that happened mid-session.
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: ({ signal }) => api.me(token!, signal),
    enabled: Boolean(token),
  });

  const liveUser = meQuery.data ?? user;

  if (!liveUser) {
    return (
      <div className="text-text-muted">Loading your profile…</div>
    );
  }

  const tenantState = liveUser.tenant_state;
  const isSandbox = tenantState === "sandbox";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-text-primary">
          Welcome, {liveUser.full_name.split(" ")[0]}
        </h1>
        <p className="mt-1 text-text-secondary">
          You&apos;re signed in to Nexus Care AI.
        </p>
      </div>

      {isSandbox ? <SandboxBanner /> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <InfoCard
          icon={<UserRound className="size-5" aria-hidden />}
          title="Your account"
          description={`${liveUser.full_name} · ${liveUser.role.replaceAll("_", " ")}`}
        />
        <InfoCard
          icon={<Building2 className="size-5" aria-hidden />}
          title="Tenant"
          description={`#${liveUser.tenant_id}`}
        />
        <InfoCard
          icon={<ShieldCheck className="size-5" aria-hidden />}
          title="Tenant state"
          description={tenantState.replaceAll("_", " ")}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>What&apos;s next</CardTitle>
          <CardDescription>
            This dashboard is intentionally minimal — it&apos;s the proof that
            auth, tenancy, and the API round-trip all work end to end. The
            real clinical surfaces (residents, eMAR, MDS, vitals, AI
            documentation assistant) land in upcoming tranches.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}

interface InfoCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

function InfoCard({ icon, title, description }: InfoCardProps) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3 pt-6">
        <span
          className="rounded-md bg-brand-100 p-2 text-brand-700"
          aria-hidden
        >
          {icon}
        </span>
        <div>
          <div className="text-sm font-medium text-text-secondary">
            {title}
          </div>
          <div className="mt-1 text-base text-text-primary">{description}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function SandboxBanner() {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-warning bg-warning/10 p-4"
    >
      <AlertTriangle
        className="mt-0.5 size-5 shrink-0 text-warning"
        aria-hidden
      />
      <div>
        <div className="font-medium text-text-primary">
          You&apos;re in a sandbox tenant.
        </div>
        <p className="text-sm text-text-secondary">
          PHI writes are blocked at the application layer. Use synthetic data
          only. Activate the tenant via the platform service before entering
          real resident information.
        </p>
      </div>
    </div>
  );
}
