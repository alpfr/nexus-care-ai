"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Card, CardContent } from "@/components/ui/card";
import { Logo } from "@/components/ui/logo";
import { FacilityCodeStep } from "@/components/login/facility-code-step";
import { PinStep } from "@/components/login/pin-step";
import { ApiError, useAuth } from "@/hooks/use-auth";

type Step = "facility" | "pin";

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, login } = useAuth();

  const [step, setStep] = useState<Step>("facility");
  const [facilityCode, setFacilityCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [errorNonce, setErrorNonce] = useState(0);

  // If already logged in, skip past login.
  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, router]);

  const handleFacility = (value: string) => {
    setFacilityCode(value);
    setError(null);
    setStep("pin");
  };

  const handleBack = () => {
    setError(null);
    setStep("facility");
  };

  const handlePinSubmit = async (pin: string) => {
    setError(null);
    try {
      await login({ facility_code: facilityCode, pin });
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Invalid login. Check your facility code and PIN.");
      } else if (err instanceof ApiError && err.status >= 500) {
        setError("The server is temporarily unavailable. Please try again.");
      } else {
        setError("Something went wrong. Please try again.");
      }
      setErrorNonce((n) => n + 1);
    }
  };

  return (
    <div className="flex min-h-dvh items-center justify-center bg-surface-base px-4 py-8">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <Card>
          <CardContent className="pt-6">
            {step === "facility" ? (
              <FacilityCodeStep
                initialValue={facilityCode}
                onSubmit={handleFacility}
              />
            ) : (
              <PinStep
                facilityCode={facilityCode}
                onBack={handleBack}
                onSubmit={handlePinSubmit}
                errorMessage={error}
                errorNonce={errorNonce}
              />
            )}
          </CardContent>
        </Card>
        <p className="mt-6 text-center text-xs text-text-muted">
          For authorized clinical staff. Do not enter real patient information
          in a sandbox tenant.
        </p>
      </div>
    </div>
  );
}
