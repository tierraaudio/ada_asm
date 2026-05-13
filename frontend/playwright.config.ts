import { defineConfig, devices, type PlaywrightTestConfig } from "@playwright/test";

const isCI = !!process.env.CI;

const config: PlaywrightTestConfig = {
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  reporter: isCI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "pnpm preview",
    port: 5173,
    reuseExistingServer: !isCI,
    timeout: 120_000,
  },
};

if (isCI) {
  config.workers = 1;
}

export default defineConfig(config);
