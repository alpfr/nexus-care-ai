"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Clock,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

const ACTIVATION_ROLES = new Set(["supervisor", "tenant_admin"]);

export default function DashboardPage() {
  const { token, user } = useAuth();
  const queryClient = useQueryClient();

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: ({ signal }) => api.me(token!, signal),
    enabled: Boolean(token),
  });

  const requestActivation = useMutation({
    mutationFn: () => api.requestActivation(token!),
    onSuccess: () => {
      // Refresh /me so the dashboard re-renders with the new state.
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });

  const liveUser = meQuery.data ?? user;

  if (!liveUser) {
    return <div className="text-text-muted">Loading your profile…</div>;
  }

  const tenantState = liveUser.tenant_state;
  const canRequestActivation = ACTIVATION_ROLES.has(liveUser.role);

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

      {tenantState === "sandbox" ? (
        <SandboxBanner
          canRequest={canRequestActivation}
          onRequest={() => requestActivation.mutate()}
          isRequesting={requestActivation.isPending}
          errorDetail={
            requestActivation.error instanceof ApiError
              ? requestActivation.error.detail
              : null
          }
        />
      ) : null}

      {tenantState === "pending_activation" ? <PendingActivationBanner /> : null}

      {tenantState === "active" ? <ActiveBanner /> : null}

      {tenantState === "suspended" || tenantState === "terminated" ? (
        <SuspendedBanner state={tenantState} />
      ) : null}

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
          <div className="text-sm font-medium text-text-secondary">{title}</div>
          <div className="mt-1 text-base text-text-primary">{description}</div>
        </div>
      </CardContent>
    </Card>
  );
}

interface SandboxBannerProps {
  canRequest: boolean;
  onRequest: () => void;
  isRequesting: boolean;
  errorDetail: string | null;
}

function SandboxBanner({
  canRequest,
  onRequest,
  isRequesting,
  errorDetail,
}: SandboxBannerProps) {
  return (
    <div
      role="status"
      className="rounded-lg border border-warning bg-warning/10 p-4"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle
          className="mt-0.5 size-5 shrink-0 text-warning"
          aria-hidden
        />
        <div className="flex-1 space-y-3">
          <div>
            <div className="font-medium text-text-primary">
              You&apos;re in a sandbox tenant.
            </div>
            <p className="text-sm text-text-secondary">
              PHI writes are blocked at the application layer. Use synthetic
              data only.{" "}
              {canRequest
                ? "When you're ready to onboard real residents, request activation. A Nexus Care AI administrator will review your BAA and identity verification."
                : "Ask your supervisor to request activation when you're ready to enter real patient information."}
            </p>
          </div>

          {canRequest ? (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                size="sm"
                onClick={onRequest}
                isLoading={isRequesting}
                disabled={isRequesting}
              >
                Request activation
              </Button>
              {errorDetail ? (
                <span role="alert" className="text-sm text-danger">
                  {errorDetail}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function PendingActivationBanner() {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-brand-300 bg-brand-50 p-4"
    >
      <Clock className="mt-0.5 size-5 shrink-0 text-brand-700" aria-hidden />
      <div>
        <div className="font-medium text-text-primary">
          Activation pending review.
        </div>
        <p className="text-sm text-text-secondary">
          A Nexus Care AI administrator is reviewing your BAA and identity
          verification. You&apos;ll be notified by email when activation is
          complete. PHI writes remain blocked until then.
        </p>
      </div>
    </div>
  );
}

function ActiveBanner() {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-success/40 bg-success/10 p-4"
    >
      <CheckCircle2
        className="mt-0.5 size-5 shrink-0 text-success"
        aria-hidden
      />
      <div>
        <div className="font-medium text-text-primary">
          Tenant is active.
        </div>
        <p className="text-sm text-text-secondary">
          PHI features are enabled. All resident data is logged in the audit
          trail and retained per your facility&apos;s retention policy.
        </p>
      </div>
    </div>
  );
}

function SuspendedBanner({ state }: { state: string }) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-danger bg-danger/10 p-4"
    >
      <AlertTriangle
        className="mt-0.5 size-5 shrink-0 text-danger"
        aria-hidden
      />
      <div>
        <div className="font-medium text-text-primary">
          Tenant is {state.replaceAll("_", " ")}.
        </div>
        <p className="text-sm text-text-secondary">
          Read access is preserved. Writes are blocked. Contact Nexus Care AI
          support to resolve.
        </p>
      </div>
    </div>
  );
}
