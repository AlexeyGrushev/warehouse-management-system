import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      port: 5173,
      // /api проксируется на backend, чтобы не думать про CORS
      proxy: {
        '/api': env.VITE_API_PROXY || 'http://localhost:8000',
      },
    },
  }
})
