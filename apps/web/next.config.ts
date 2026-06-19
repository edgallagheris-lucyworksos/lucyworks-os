import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: { externalDir: true },
  async rewrites() {
    return [
      {
        source: "/resource-directory",
        destination: "/resources",
      },
    ];
  },
};

export default nextConfig;
