import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // Built straight into the backend package, so one container serves both halves and there is
  // no CORS layer to configure.
  build: { outDir: '../app/static', emptyOutDir: true },
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
})
