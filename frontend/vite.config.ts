/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// No VITE_API_URL anywhere on purpose. See docs/adr/0002-frontend-runtime-config.md:
// a Vite build inlines import.meta.env at BUILD time, so baking the backend URL in
// would produce one image per environment and destroy build-once-deploy-many.
// In dev we proxy /api to the backend; in a container nginx does the same job.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
