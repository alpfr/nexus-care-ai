import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import { QueryProvider } from "@/providers/query-provider";

export const metadata: Metadata = {
  title: "Nexus Care AI",
  description:
    "AI-native EHR for Post-Acute and Long-Term Care.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1, // prevent iOS double-tap zoom on PIN keypad
  themeColor: "#0e9488", // teal-ish, matches brand
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
