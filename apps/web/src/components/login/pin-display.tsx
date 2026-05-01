"use client";

import { cn } from "@/lib/cn";

interface PinDisplayProps {
  length: number;
  filled: number;
  invalid?: boolean;
}

/**
 * Visual indicator for PIN entry — N dots that fill in as the user types.
 * Doesn't show the actual digits (shoulder-surfing protection).
 */
export function PinDisplay({ length, filled, invalid = false }: PinDisplayProps) {
  return (
    <div
      role="status"
      aria-label={`PIN: ${filled} of ${length} digits entered`}
      className="flex items-center justify-center gap-3"
    >
      {Array.from({ length }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "size-4 rounded-full transition-colors",
            i < filled
              ? invalid
                ? "bg-danger"
                : "bg-brand-600"
              : "border-2 border-surface-border bg-surface-card",
          )}
          aria-hidden
        />
      ))}
    </div>
  );
}
