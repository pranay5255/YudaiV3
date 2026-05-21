import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'https://yudai.app';
const isCI = Boolean(process.env.CI);

export default defineConfig({
  expect: {
    timeout: 15_000,
  },
  forbidOnly: isCI,
  fullyParallel: false,
  outputDir: 'test-results',
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  retries: isCI ? 2 : 0,
  testDir: './e2e',
  timeout: 90_000,
  use: {
    actionTimeout: 20_000,
    baseURL,
    navigationTimeout: 45_000,
    screenshot: 'only-on-failure',
    trace: 'off',
    video: 'off',
  },
  workers: 1,
});
