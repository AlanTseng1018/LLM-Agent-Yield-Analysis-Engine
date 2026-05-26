import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // In production the FastAPI backend serves the built `dist/` itself, so
  // frontend code uses relative paths (e.g. `/agent/stream`). The proxy below
  // lets `npm run dev` on :5173 still reach the backend on :8000 unchanged.
  server: {
    proxy: {
      '/agent':  { target: 'http://localhost:8000', changeOrigin: true, ws: true },
      '/chat':   { target: 'http://localhost:8000', changeOrigin: true, ws: true },
      '/report': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
