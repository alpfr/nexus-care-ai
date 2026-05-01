import { cn } from "@/lib/cn";

interface LogoProps {
  className?: string;
}

/**
 * Placeholder wordmark.
 *
 * A simple SVG glyph (a stylized "n" inside a rounded square) plus the
 * product name in a sans-serif. Replace this whole component when real
 * branding lands — the only thing that depends on its shape is the
 * vertical rhythm in the login screen, which is generous enough to absorb
 * a different mark.
 */
export function Logo({ className }: LogoProps) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <svg
        width="40"
        height="40"
        viewBox="0 0 40 40"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden
      >
        <rect
          x="0"
          y="0"
          width="40"
          height="40"
          rx="10"
          className="fill-brand-600"
        />
        <path
          d="M11 28 V14 H15 L25 24 V14 H29 V28 H25 L15 18 V28 Z"
          className="fill-text-onbrand"
        />
      </svg>
      <div className="leading-tight">
        <div className="text-lg font-semibold text-text-primary">
          Nexus Care
        </div>
        <div className="text-xs uppercase tracking-wider text-text-muted">
          AI · Long-Term Care
        </div>
      </div>
    </div>
  );
}
