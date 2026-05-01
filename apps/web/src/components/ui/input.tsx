"use client";

import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ invalid, className, ...rest }, ref) => {
    return (
      <input
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cn(
          "h-12 w-full rounded-md border bg-surface-card px-3 text-base",
          "text-text-primary placeholder:text-text-muted",
          "transition-colors",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500",
          "disabled:cursor-not-allowed disabled:opacity-60",
          invalid
            ? "border-danger"
            : "border-surface-border focus-visible:border-brand-500",
          className,
        )}
        {...rest}
      />
    );
  },
);
Input.displayName = "Input";
