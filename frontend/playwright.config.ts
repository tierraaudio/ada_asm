import { defineConfig, devices, type PlaywrightTestConfig } from "@playwright/test";

const isCI = !!process.env.CI;
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173";
// When PLAYWRIGHT_BASE_URL is supplied (e.g. the docker stack at :15173) we
// trust the operator's running stack and skip starting our own preview server.
const useExternalServer = !!process.env.PLAYWRIGHT_BASE_URL;

const config: PlaywrightTestConfig = {
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  reporter: isCI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
};

if (!useExternalServer) {
  config.webServer = {
    command: "pnpm preview",
    port: 5173,
    reuseExistingServer: !isCI,
    timeout: 120_000,
  };
}

if (isCI) {
  config.workers = 1;
}

export default defineConfig(config);
