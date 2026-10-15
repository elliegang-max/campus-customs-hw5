import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API runs on :8000 (started from backend/ with `uvicorn main:app`).
// Proxying keeps every request same-origin in development, so the browser never
// needs a CORS preflight and the app can use plain relative URLs.
//
// VITE_API_TARGET overrides the target when the backend is on another port —
// useful when something else already holds 8000.
const target = process.env.VITE_API_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': target,
    },
  },
})
