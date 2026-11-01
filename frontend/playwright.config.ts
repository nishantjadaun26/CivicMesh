import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  webServer: {
    command: 'npm run preview -- --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    timeout: 15000,
  },
  use: {
    baseURL: 'http://127.0.0.1:4173',
    channel: 'msedge',
    headless: false,
    trace: 'retain-on-failure',
  },
  reporter: 'list',
});
