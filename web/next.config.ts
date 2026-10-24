import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  // A separate output dir lets a production build run while `next dev` is serving.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
