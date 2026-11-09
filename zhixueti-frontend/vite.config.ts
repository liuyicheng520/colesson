import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import type { IncomingMessage, ServerResponse } from 'http'
import type { ClientRequest } from 'http'

function isSseProxyRequest(url?: string | null): boolean {
  return !!url && url.includes('/stream')
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    target: 'es2019',
    // 三方库单独成块：首屏只需加载业务代码，图表与组件库可按路由缓存
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ['echarts/core', 'echarts/charts', 'echarts/components', 'echarts/renderers'],
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
          markdown: ['markdown-it', 'highlight.js'],
          vendor: ['vue', 'vue-router', 'pinia', 'axios', 'dayjs'],
        },
      },
    },
    // element-plus 为完整引入的单一供应商块（首次加载后长期缓存），单独放宽阈值
    chunkSizeWarningLimit: 1200,
  },
  server: {
    host: true,
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyReq', (proxyReq: ClientRequest, req: IncomingMessage, _res: ServerResponse, options) => {
            if (isSseProxyRequest(req.url)) {
              ;(options as { selfHandleResponse?: boolean }).selfHandleResponse = true
              proxyReq.setHeader('Accept', 'text/event-stream')
            }
          })
          proxy.on('proxyRes', (proxyRes, req: IncomingMessage, res: ServerResponse) => {
            if (!isSseProxyRequest(req.url)) return
            const headers: Record<string, string | string[] | undefined> = { ...proxyRes.headers }
            delete headers['content-length']
            headers['cache-control'] = 'no-cache, no-transform'
            headers.connection = 'keep-alive'
            headers['x-accel-buffering'] = 'no'
            if (!headers['content-type']) {
              headers['content-type'] = 'text/event-stream; charset=utf-8'
            }
            res.writeHead(proxyRes.statusCode ?? 200, headers)
            proxyRes.pipe(res)
            proxyRes.on('error', () => {
              if (!res.writableEnded) res.end()
            })
          })
        },
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/assets/styles/variables.scss" as *;`,
      },
    },
  },
})
