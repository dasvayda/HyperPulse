import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Keep verification builds separate from an already running dev server.
  distDir: process.env.NEXT_BUILD_DIR || ".next",
};

export default nextConfig;
