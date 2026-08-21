import { defineConfig, devices } from "@playwright/test";

const externalServer = process.env.LAUNCHPAD_E2E_SKIP_WEBSERVER === "1";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.LAUNCHPAD_E2E_WEB_BASE_URL ?? "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  ...(externalServer
    ? {}
    : {
        webServer: {
          command: "npm run dev -- --host 127.0.0.1 --port 3000",
          url: "http://127.0.0.1:3000",
          reuseExistingServer: true,
          timeout: 120_000,
        },
      }),
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
});
