import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  webServer: {
    command: 'npm run preview -- --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
    env: { VITE_API_URL: '', VITE_SUPABASE_URL: '', VITE_SUPABASE_ANON_KEY: '', VITE_MAP_TILE_URL: '', VITE_MAP_ATTRIBUTION: '' },
    timeout: 15000,
  },
  use: {
    baseURL: 'http://127.0.0.1:4173',
    channel: process.env.CI ? undefined : 'msedge',
    headless: true,
    trace: 'retain-on-failure',
  },
  reporter: 'list',
});
