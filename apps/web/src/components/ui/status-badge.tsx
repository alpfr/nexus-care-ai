"use client";

import { cn } from "@/lib/cn";

type Tone = "success" | "warning" | "danger" | "neutral" | "info";

const toneStyles: Record<Tone, string> = {
  success: "bg-emerald-100 text-emerald-900 border-emerald-200",
  warning: "bg-amber-100 text-amber-900 border-amber-200",
  danger: "bg-rose-100 text-rose-900 border-rose-200",
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
  info: "bg-sky-100 text-sky-900 border-sky-200",
};

export function StatusBadge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        toneStyles[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
