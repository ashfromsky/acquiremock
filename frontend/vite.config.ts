import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendTarget = 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    fs: {
      allow: ['..'],
    },
    proxy: {
      '/api': backendTarget,
      '/health': backendTarget,
      '/webhooks': backendTarget,
      '/checkout': backendTarget,
      '/otp': backendTarget,
      '/success': backendTarget,
      '/static': backendTarget,
      '/docs': backendTarget,
      '/redoc': backendTarget,
      '/openapi.json': backendTarget,
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
  },
});
