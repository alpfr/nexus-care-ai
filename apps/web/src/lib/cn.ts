import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combine class names safely, with Tailwind class deduplication.
 *
 * Use this everywhere you compose className strings. It handles conditionals
 * (`cn("foo", isActive && "bar")`) and merges conflicting Tailwind utilities
 * so the last one wins (`cn("p-2", "p-4")` → `"p-4"`).
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
