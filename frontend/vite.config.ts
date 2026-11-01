import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  for (const [name, value] of Object.entries(env)) {
    if (/SECRET|SERVICE_ROLE|GEMINI|PRIVATE|PASSWORD/i.test(name) || value.startsWith('sb_secret_')) {
      throw new Error(`Server-only credentials must not be set in ${name}.`);
    }
  }
  const key = env.VITE_SUPABASE_ANON_KEY;
  if (key?.split('.').length === 3) {
    try {
      if (JSON.parse(Buffer.from(key.split('.')[1], 'base64url').toString()).role === 'service_role') {
        throw new Error('A service-role key cannot be included in a browser build.');
      }
    } catch (error) {
      if (error instanceof Error && error.message.includes('service-role')) throw error;
    }
  }
  return { plugins: [react()] };
});
