import { defineConfig } from '@playwright/test';
import path from 'node:path';

export default defineConfig({
  testDir: './integration-tests', workers: 1, timeout: 45000,
  webServer: [
    {
      command: `"${path.resolve('..', 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')}" -m backend.tests.browser_server`,
      url: 'http://127.0.0.1:8766/health/live', timeout: 30000, reuseExistingServer: false,
      env: { PYTHONPATH: '..', ENVIRONMENT: 'test', CORS_ORIGINS: 'http://127.0.0.1:4174',
        SUPABASE_URL: 'https://isolated-project.supabase.test', SUPABASE_JWT_SECRET: 'isolated-browser-test-secret-never-used-in-runtime',
        SUPABASE_SERVICE_ROLE_KEY: '', PILOT_LOCALITY_NAME: 'Isolated test jurisdiction', PILOT_LATITUDE: '1', PILOT_LONGITUDE: '2' },
    },
    { command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4174 --strictPort', url: 'http://127.0.0.1:4174', timeout: 15000, reuseExistingServer: false,
      env: { VITE_API_URL: 'http://127.0.0.1:8766', VITE_SUPABASE_URL: 'https://isolated-project.supabase.test',
        VITE_SUPABASE_ANON_KEY: 'isolated-public-browser-key', VITE_MAP_TILE_URL: '', VITE_MAP_ATTRIBUTION: '' } },
  ],
  use: { baseURL: 'http://127.0.0.1:4174', channel: process.env.CI ? undefined : 'msedge', headless: true, trace: 'retain-on-failure' },
  reporter: 'list',
});
