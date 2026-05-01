"use client";

import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { PinDisplay } from "./pin-display";
import { PinKeypad } from "./pin-keypad";

interface PinStepProps {
  facilityCode: string;
  onBack: () => void;
  onSubmit: (pin: string) => Promise<void>;
  errorMessage?: string | null;
  /** When the parent receives a new error, bump this so we can clear PIN. */
  errorNonce?: number;
}

const PIN_LENGTH = 6;

export function PinStep({
  facilityCode,
  onBack,
  onSubmit,
  errorMessage,
  errorNonce,
}: PinStepProps) {
  const [pin, setPin] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Clear the PIN any time the parent reports a new error.
  useEffect(() => {
    if (errorNonce !== undefined) {
      setPin("");
    }
  }, [errorNonce]);

  // Auto-submit when the PIN reaches full length.
  useEffect(() => {
    if (pin.length === PIN_LENGTH && !submitting) {
      setSubmitting(true);
      void onSubmit(pin).finally(() => setSubmitting(false));
    }
  }, [pin, submitting, onSubmit]);

  // Allow physical keyboard digit entry as well — bedside tablet might be
  // docked with a keyboard, plus this is friendlier in dev.
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (submitting) return;
      if (/^\d$/.test(e.key)) {
        setPin((p) => (p.length < PIN_LENGTH ? p + e.key : p));
      } else if (e.key === "Backspace") {
        setPin((p) => p.slice(0, -1));
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [submitting]);

  const handleDigit = (d: string) => {
    setPin((p) => (p.length < PIN_LENGTH ? p + d : p));
  };

  const handleBackspace = () => {
    setPin((p) => p.slice(0, -1));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onBack}
          disabled={submitting}
        >
          <ArrowLeft className="size-4" aria-hidden />
          Change facility
        </Button>
        <span className="text-sm text-text-muted">
          {facilityCode}
        </span>
      </div>

      <div className="space-y-2 text-center">
        <h2 className="text-xl font-semibold text-text-primary">
          Enter your PIN
        </h2>
        <p className="text-sm text-text-secondary">
          {PIN_LENGTH}-digit PIN provided by your facility.
        </p>
      </div>

      <PinDisplay
        length={PIN_LENGTH}
        filled={pin.length}
        invalid={Boolean(errorMessage)}
      />

      {errorMessage ? (
        <p role="alert" className="text-center text-sm text-danger">
          {errorMessage}
        </p>
      ) : null}

      <PinKeypad
        onDigit={handleDigit}
        onBackspace={handleBackspace}
        disabled={submitting}
      />
    </div>
  );
}
