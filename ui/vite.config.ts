import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// A API (uv run galaxies-api) roda em :8000; o proxy evita CORS no desenvolvimento.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', rewrite: (p) => p.replace(/^\/api/, '') } } },
})
