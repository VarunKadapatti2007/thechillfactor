import type { NextConfig } from "next";

const exporting = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = {
  devIndicators: false,
  // A separate output dir lets a production build run while `next dev` is serving.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Static export for Firebase Hosting (the app renders entirely in the browser).
  ...(exporting ? { output: "export" as const, trailingSlash: false } : {}),
};

export default nextConfig;
