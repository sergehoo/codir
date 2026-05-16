import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Cible du proxy `/api` :
 *   - défaut : Django local sur :8000
 *   - override : VITE_PROXY_TARGET dans .env.local
 *     (ex. VITE_PROXY_TARGET=https://codir.datarium-dev.com)
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://localhost:8000'
  const isHttps = proxyTarget.startsWith('https://')

  return {
    plugins: [react()],
    resolve: { alias: { '@': path.resolve(__dirname, './src') } },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: !isHttps ? true : false, // accepte cert self-signed prod
          ws: true,                          // pour les WebSockets ASGI
        },
      },
    },
  }
})
