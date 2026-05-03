"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { api, ApiError, type CreateResidentRequest } from "@/lib/api";

const schema = z.object({
  legal_first_name: z.string().min(1, "Required").max(100),
  legal_last_name: z.string().min(1, "Required").max(100),
  preferred_name: z.string().max(100).optional(),
  date_of_birth: z.string().min(1, "Required"),
  gender: z.string().max(50).optional(),
  admission_date: z.string().min(1, "Required"),
  room: z.string().max(16).optional(),
  bed: z.string().max(16).optional(),
  allergies_summary: z.string().optional(),
  code_status: z.enum(["full", "dnr", "dni", "dnr_dni", "comfort_only", "unknown"]),
  fall_risk: z.enum(["low", "moderate", "high", "unassessed"]),
  primary_physician_name: z.string().max(200).optional(),
  emergency_contact_name: z.string().max(200).optional(),
  emergency_contact_relationship: z.string().max(64).optional(),
  emergency_contact_phone: z.string().max(32).optional(),
  chart_note: z.string().optional(),
});
type FormData = z.infer<typeof schema>;

export default function AdmitResidentPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, user } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (mounted && user && user.role !== "supervisor" && user.role !== "tenant_admin") {
      router.replace("/dashboard/residents");
    }
  }, [mounted, user, router]);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      code_status: "unknown",
      fall_risk: "unassessed",
      admission_date: new Date().toISOString().slice(0, 10),
    },
  });

  const mutation = useMutation({
    mutationFn: (payload: CreateResidentRequest) => api.admitResident(token!, payload),
    onSuccess: (resident) => {
      queryClient.invalidateQueries({ queryKey: ["residents"] });
      router.replace(`/dashboard/residents/${resident.id}`);
    },
  });

  if (!mounted) return <div className="text-text-muted">Loading…</div>;

  const onSubmit = handleSubmit(async (data) => {
    try {
      // Strip empty strings → undefined so backend validators don't trip.
      const cleaned: CreateResidentRequest = Object.fromEntries(
        Object.entries(data).map(([k, v]) => [k, v === "" ? undefined : v]),
      ) as CreateResidentRequest;
      await mutation.mutateAsync(cleaned);
    } catch (e) {
      if (e instanceof ApiError) {
        setError("root", { message: e.detail });
      } else {
        setError("root", { message: "Could not admit resident" });
      }
    }
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        href="/dashboard/residents"
        className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text-primary"
      >
        <ArrowLeft className="size-4" aria-hidden /> All residents
      </Link>

      <div>
        <h1 className="text-2xl font-semibold text-text-primary">Admit resident</h1>
        <p className="text-sm text-text-muted">
          Required fields are marked with an asterisk.
        </p>
      </div>

      <form
        onSubmit={onSubmit}
        className="space-y-6 rounded-xl border border-surface-border bg-surface-card p-6"
      >
        {errors.root ? (
          <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
            {errors.root.message}
          </div>
        ) : null}

        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="col-span-full text-sm font-semibold uppercase tracking-wide text-text-muted">
            Identity
          </legend>
          <div>
            <label className="mb-1 block text-sm font-medium">Legal first name *</label>
            <Input {...register("legal_first_name")} />
            {errors.legal_first_name ? (
              <p className="mt-1 text-xs text-rose-700">{errors.legal_first_name.message}</p>
            ) : null}
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Legal last name *</label>
            <Input {...register("legal_last_name")} />
            {errors.legal_last_name ? (
              <p className="mt-1 text-xs text-rose-700">{errors.legal_last_name.message}</p>
            ) : null}
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Preferred name</label>
            <Input {...register("preferred_name")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Gender</label>
            <Input {...register("gender")} placeholder="Optional" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Date of birth *</label>
            <Input type="date" {...register("date_of_birth")} />
            {errors.date_of_birth ? (
              <p className="mt-1 text-xs text-rose-700">{errors.date_of_birth.message}</p>
            ) : null}
          </div>
        </fieldset>

        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="col-span-full text-sm font-semibold uppercase tracking-wide text-text-muted">
            Admission
          </legend>
          <div>
            <label className="mb-1 block text-sm font-medium">Admission date *</label>
            <Input type="date" {...register("admission_date")} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="mb-1 block text-sm font-medium">Room</label>
              <Input {...register("room")} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Bed</label>
              <Input {...register("bed")} />
            </div>
          </div>
        </fieldset>

        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="col-span-full text-sm font-semibold uppercase tracking-wide text-text-muted">
            Clinical
          </legend>
          <div>
            <label className="mb-1 block text-sm font-medium">Code status</label>
            <select
              {...register("code_status")}
              className="block h-11 w-full rounded-md border border-surface-border bg-surface-card px-3"
            >
              <option value="unknown">Unknown</option>
              <option value="full">Full code</option>
              <option value="dnr">DNR</option>
              <option value="dni">DNI</option>
              <option value="dnr_dni">DNR/DNI</option>
              <option value="comfort_only">Comfort only</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Fall risk</label>
            <select
              {...register("fall_risk")}
              className="block h-11 w-full rounded-md border border-surface-border bg-surface-card px-3"
            >
              <option value="unassessed">Unassessed</option>
              <option value="low">Low</option>
              <option value="moderate">Moderate</option>
              <option value="high">High</option>
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm font-medium">Allergies summary</label>
            <textarea
              {...register("allergies_summary")}
              rows={2}
              className="block w-full rounded-md border border-surface-border bg-surface-card px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Primary physician</label>
            <Input {...register("primary_physician_name")} />
          </div>
        </fieldset>

        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="col-span-full text-sm font-semibold uppercase tracking-wide text-text-muted">
            Emergency contact
          </legend>
          <div>
            <label className="mb-1 block text-sm font-medium">Name</label>
            <Input {...register("emergency_contact_name")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Relationship</label>
            <Input {...register("emergency_contact_relationship")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Phone</label>
            <Input {...register("emergency_contact_phone")} />
          </div>
        </fieldset>

        <div className="flex justify-end gap-3 pt-2">
          <Link href="/dashboard/residents">
            <Button variant="ghost" type="button">Cancel</Button>
          </Link>
          <Button type="submit" isLoading={isSubmitting || mutation.isPending}>
            Admit
          </Button>
        </div>
      </form>
    </div>
  );
}
