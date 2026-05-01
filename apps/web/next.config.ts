import type { NextConfig } from "next";

/**
 * Nexus Care AI — Next.js config.
 *
 * The /api/* rewrite proxies browser requests to the FastAPI backend during
 * development. This keeps the browser thinking everything is same-origin
 * (no CORS preflight) and lets us use a single base URL across env boundaries.
 *
 * In production (Phase 5+), the same rewrite is handled by the ingress
 * (nginx / GKE Gateway), so this config block becomes a no-op.
 */
const config: NextConfig = {
  reactStrictMode: true,

  async rewrites() {
    const apiBase =
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:18001";
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(self), microphone=(self), geolocation=()",
          },
        ],
      },
    ];
  },
};

export default config;
