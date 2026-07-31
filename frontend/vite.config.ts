import path from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const BACKEND = 'http://127.0.0.1:8000'

/**
 * 同域是 httpOnly Cookie 方案的**硬性前提**（F-ADR-002）。
 *
 * 浏览器只访问 :5173，Vite 把这些路径转发到 Django——全程单一源，
 * 既能自动带 Cookie，也完全不需要 CORS。
 *
 * 生产环境用 Nginx 做同样的事（见 deploy/nginx.conf）。
 */
const PROXY_PATHS = ['/api', '/django', '/admin', '/static']

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      PROXY_PATHS.map((p) => [
        p,
        {
          target: BACKEND,
          // ⚠️ 必须是 false。
          //
          // changeOrigin: true 会把转发请求的 Host 头改写成 127.0.0.1:8000，
          // 而 Django 的 CSRF 校验要比对 Origin/Referer 与 Host——
          // 改写之后会出现「CSRF verification failed」，
          // 而且报错信息完全指不到真正的原因。
          changeOrigin: false,
        },
      ]),
    ),
  },
})
