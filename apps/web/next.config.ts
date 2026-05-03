import type { NextConfig } from "next";

/**
 * Nexus Care AI — Next.js config.
 *
 * The /api/* rewrite proxies browser requests to the FastAPI backend. In
 * dev that's localhost:18001; in containers it's the Kubernetes Service
 * DNS name (configured via NEXT_PUBLIC_API_BASE_URL at build/runtime).
 *
 * `output: "standalone"` makes `next build` emit a self-contained bundle
 * under `.next/standalone/` — used by the production Docker image.
 */
const config: NextConfig = {
  reactStrictMode: true,
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,

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
