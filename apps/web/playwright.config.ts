import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/ui",
  timeout: 45_000,
  fullyParallel: false,
  retries: 0,
  reporter: [["line"]],
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "mkdir -p .next/standalone/apps/web/.next/static .next/standalone/apps/web/public && cp -R .next/static/. .next/standalone/apps/web/.next/static/ && cp -R public/. .next/standalone/apps/web/public/ && HOSTNAME=127.0.0.1 PORT=3000 node .next/standalone/apps/web/server.js",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
