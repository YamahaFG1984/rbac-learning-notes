import path from 'node:path'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const BACKEND = 'http://127.0.0.1:8000'

/**
 * 同域是 httpOnly Cookie 方案的**硬性前提**（F-ADR-002）。
 *
 * 浏览器只访问 :5174，Vite 把这些路径转发到 Django——全程单一源，
 * 既能自动带 Cookie，也完全不需要 CORS。
 *
 * 生产环境用 Nginx 做同样的事（见 deploy/nginx.conf）。
 *
 * ⚠️ 本文件与 React 版（frontend/vite.config.ts）的差异**只有三处**：
 *    plugins、server.port、preview.port。
 *
 *    这是本阶段的第一个结论，而且它出现得比预想的早：
 *    **同域代理是构建工具的事，与前端框架完全无关。**
 *    F-ADR-002 这条影响深远的决策，换框架时的迁移成本是零。
 */
const PROXY_PATHS = ['/api', '/django', '/admin', '/static']

const proxy = Object.fromEntries(
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
)

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  // ⚠️ 5174 而不是 5173：React 版占着 5173，两个前端要能同时开着做对照
  //    （docs/vue-frontend/03-实施计划.md 第 2 节）。
  server: { port: 5174, proxy },
  // ⚠️ preview 的代理配置是**独立的一份**，不继承 server.proxy。
  //
  //    E2E 跑在 `vite preview`（生产构建）上而不是 dev server 上：
  //    dev server 每个请求都要现场转译模块，在小内存机器上会把
  //    整个测试套件拖垮——表现是随机超时、每次红的用例都不一样，
  //    极容易被误判成「E2E 就是不稳定」而加 retry 盖过去。
  //
  //    跑生产构建还有一个好处：测的就是用户实际拿到的那份代码。
  preview: { port: 5174, proxy },
})
