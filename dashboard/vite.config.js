import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/logs': 'http://localhost:8000',
      '/anomalies': 'http://localhost:8000',
      '/clusters': 'http://localhost:8000',
      '/alerts': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/seed': 'http://localhost:8000',
    },
  },
})
