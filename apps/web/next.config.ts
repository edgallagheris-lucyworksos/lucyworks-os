import type { NextConfig } from "next";

const apiInternalBase = (process.env.API_INTERNAL_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: { externalDir: true },
  async rewrites() {
    return [
      {
        source: "/resource-directory",
        destination: "/resources",
      },
      {
        source: "/api/:path*",
        destination: `${apiInternalBase}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
