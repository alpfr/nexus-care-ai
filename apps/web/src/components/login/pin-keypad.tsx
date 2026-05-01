"use client";

import { Delete } from "lucide-react";

import { cn } from "@/lib/cn";

interface PinKeypadProps {
  onDigit: (digit: string) => void;
  onBackspace: () => void;
  disabled?: boolean;
}

const DIGITS: ReadonlyArray<string | null> = [
  "1", "2", "3",
  "4", "5", "6",
  "7", "8", "9",
  null, "0", "<<", // bottom row: spacer, 0, backspace
];

/**
 * Large on-screen numeric keypad for PIN entry.
 *
 * Designed for bedside-tablet use during med-pass — buttons are big enough
 * to hit reliably with gloves, and the layout matches a physical phone
 * keypad so muscle memory transfers.
 */
export function PinKeypad({
  onDigit,
  onBackspace,
  disabled = false,
}: PinKeypadProps) {
  return (
    <div
      role="group"
      aria-label="PIN keypad"
      className="grid grid-cols-3 gap-3"
    >
      {DIGITS.map((value, index) => {
        if (value === null) {
          return <div key={index} aria-hidden />;
        }
        if (value === "<<") {
          return (
            <KeyButton
              key={index}
              ariaLabel="Backspace"
              onClick={onBackspace}
              disabled={disabled}
              variant="utility"
            >
              <Delete className="size-6" aria-hidden />
            </KeyButton>
          );
        }
        return (
          <KeyButton
            key={index}
            ariaLabel={`Digit ${value}`}
            onClick={() => onDigit(value)}
            disabled={disabled}
          >
            {value}
          </KeyButton>
        );
      })}
    </div>
  );
}

interface KeyButtonProps {
  ariaLabel: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: "digit" | "utility";
  children: React.ReactNode;
}

function KeyButton({
  ariaLabel,
  onClick,
  disabled,
  variant = "digit",
  children,
}: KeyButtonProps) {
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "h-16 rounded-lg text-2xl font-medium",
        "transition-colors active:scale-[0.97]",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variant === "digit"
          ? "bg-surface-muted text-text-primary hover:bg-surface-border"
          : "bg-surface-card text-text-secondary border border-surface-border hover:bg-surface-muted",
      )}
    >
      {children}
    </button>
  );
}
