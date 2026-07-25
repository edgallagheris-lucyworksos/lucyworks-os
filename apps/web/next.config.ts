import path from "node:path";
import type { NextConfig } from "next";

const apiInternalBase = (process.env.API_INTERNAL_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const legacyApiPrefix = "/_lucyworks_api";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "../.."),
  experimental: { externalDir: true },
  // Older screens already read NEXT_PUBLIC_API_BASE before their localhost
  // fallback. Supplying a non-empty same-origin prefix here makes that fallback
  // unreachable in every supported dev and production build while the screens
  // are progressively moved to the shared API client.
  env: {
    NEXT_PUBLIC_API_BASE: legacyApiPrefix,
  },
  async rewrites() {
    return [
      {
        source: "/resource-directory",
        destination: "/resources",
      },
      {
        source: `${legacyApiPrefix}/api/:path*`,
        destination: `${apiInternalBase}/api/:path*`,
      },
      {
        source: "/api/:path*",
        destination: `${apiInternalBase}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
