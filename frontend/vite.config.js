import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// © 2026 cwl. All rights reserved.
export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        banner: '/* © 2026 cwl - Knowledge Agent */'
      }
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        proxyTimeout: 120000,
        timeout: 120000,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            if (req.url?.includes('/knowledge/stream')) {
              proxyReq.setHeader('Accept', 'text/event-stream')
              proxyReq.setHeader('Accept-Encoding', 'identity')
            }
          })
        },
        // 不重写路径，保持 /api/v1 结构
      }
    }
  }
})