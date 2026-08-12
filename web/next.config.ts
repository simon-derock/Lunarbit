import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    // The compiler API is more reliable than the spawned CLI in managed runtimes.
    useTypeScriptCli: false,
  },
};

export default nextConfig;
