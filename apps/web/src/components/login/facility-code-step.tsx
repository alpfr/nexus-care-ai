"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const schema = z.object({
  facility_code: z
    .string()
    .min(3, "Facility code is too short")
    .max(32, "Facility code is too long")
    .regex(
      /^[a-z0-9-]+$/i,
      "Facility code may only contain letters, numbers, and dashes",
    ),
});

type FormValues = z.infer<typeof schema>;

interface FacilityCodeStepProps {
  initialValue?: string;
  onSubmit: (facilityCode: string) => void;
}

export function FacilityCodeStep({ initialValue, onSubmit }: FacilityCodeStepProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { facility_code: initialValue ?? "" },
  });

  return (
    <form
      onSubmit={handleSubmit((values) =>
        onSubmit(values.facility_code.trim().toLowerCase()),
      )}
      className="space-y-5"
      noValidate
    >
      <div className="space-y-2">
        <label
          htmlFor="facility_code"
          className="block text-sm font-medium text-text-primary"
        >
          Facility code
        </label>
        <Input
          id="facility_code"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          inputMode="text"
          placeholder="demo-sandbox"
          invalid={Boolean(errors.facility_code)}
          {...register("facility_code")}
        />
        {errors.facility_code ? (
          <p
            role="alert"
            className="text-sm text-danger"
          >
            {errors.facility_code.message}
          </p>
        ) : (
          <p className="text-sm text-text-muted">
            Provided by your facility administrator.
          </p>
        )}
      </div>
      <Button
        type="submit"
        size="lg"
        className="w-full"
        isLoading={isSubmitting}
      >
        Continue
        <ArrowRight className="size-5" aria-hidden />
      </Button>
    </form>
  );
}
