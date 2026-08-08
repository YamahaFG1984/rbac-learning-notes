# vue-v0.1.0 — 前端骨架与同域代理

| 项 | 值 |
| --- | --- |
| 需求 | — |
| 关键 V-ADR | [001](../02-设计文档.md)、[002](../02-设计文档.md)、[014](../02-设计文档.md) |
| 预计耗时 | 2 ~ 3 小时 |
| 变更规模 | ~200 行（不含 lock 文件） |
| 上一个 tag | `vue-v0.0.1-docs` |
| React 对应 | [`fe-v0.1.0`](../../frontend/tags/01-fe-v0.1.0-前端骨架与同域代理.md) |

---

## 一、动手之前，先自己想清楚

1. 后端已经在跑了（Session 认证、CSRF、`/api/v1/` 全都现成）。
   **这个 tag 需要改后端吗？** 如果你的答案是「要」，先停下来想清楚要改什么。
2. React 版用了 5173，Vue 版用什么端口？**两个能同时开着吗？**
3. `vite.config.ts` 里的 `changeOrigin` 该设什么？为什么？
4. `tsconfig` 里 React 版用 `tsc -b`，Vue 版为什么必须换成别的？

---

## 二、交付物清单

| 操作 | 文件 | 职责 |
| --- | --- | --- |
| 新建 | `frontend-vue/package.json` | 依赖与脚本 |
| 新建 | `frontend-vue/vite.config.ts` | 同域代理（**逐字对照 React 版**） |
| 新建 | `frontend-vue/tsconfig*.json` | TS strict |
| 新建 | `frontend-vue/index.html` | 入口 |
| 新建 | `frontend-vue/src/main.ts` | 挂载 app + 注册 pinia / router / antdv |
| 新建 | `frontend-vue/src/App.vue` | 根组件 |
| 新建 | `frontend-vue/src/router/index.ts` | 只有一条 `/` 路由 |
| 新建 | `frontend-vue/src/api/client.ts` | axios 实例（**从 React 版复制**） |
| 修改 | `.gitignore` | 加 `frontend-vue/dist`、`frontend-vue/node_modules` |
| 修改 | `README.md` | 三套前端的入口 |

> ⚠️ 本 tag **一行后端代码都不该改**。第一节第 1 问的答案是「不需要」——
> React 阶段的 `BE-1` ~ `BE-7` 已经全做完了。
> 如果你发现自己在改 `config/settings/`，说明走错方向了。

---

## 三、依赖版本

```jsonc
{
  "dependencies": {
    "vue": "^3.5.41",
    "vue-router": "^5.2.0",          // ⚠️ classic API，见 V-ADR-013
    "pinia": "^4.0.2",
    "ant-design-vue": "^4.2.6",
    "@ant-design/icons-vue": "^7.0.1",
    "@tanstack/vue-query": "^5.101.4",  // 与 React 版**同版本号**
    "axios": "^1.19.0"                  // 与 React 版相同
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^6.0.8",
    "vue-tsc": "^3.3.9",                // ← 替代 tsc
    "vite": "^8.2.0",                   // 与 React 版相同
    "typescript": "~6.0.2"              // 与 React 版相同
  }
}
```

第一节第 4 问：`tsc` **不认识 `.vue` 文件**。`vue-tsc` 是它的包装，
先把 SFC 的 `<script>` 抽出来再交给 `tsc`。

```jsonc
"scripts": {
  "dev": "vite",
  "build": "vue-tsc -b && vite build",
  "typecheck": "vue-tsc -b --noEmit",
  "preview": "vite preview"
}
```

---

## 四、同域代理

**⚠️ 这个文件应该和 React 版几乎逐字相同。** 先自己写，再 diff：

```bash
diff -u frontend/vite.config.ts frontend-vue/vite.config.ts
```

**期望的差异只有三行**：`plugins`、`server.port`、`preview.port`。

```ts
const BACKEND = 'http://127.0.0.1:8000'
const PROXY_PATHS = ['/api', '/django', '/admin', '/static']

const proxy = Object.fromEntries(
  PROXY_PATHS.map((p) => [p, {
    target: BACKEND,
    // ⚠️ 必须是 false。
    //    changeOrigin: true 会把 Host 头改写成 127.0.0.1:8000，
    //    而 Django 的 CSRF 校验要比对 Origin/Referer 与 Host——
    //    改写之后会出现「CSRF verification failed」，
    //    而且报错信息完全指不到真正的原因。
    changeOrigin: false,
  }]),
)

export default defineConfig({
  plugins: [vue()],                                    // ← 唯一的实质差异
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
  server: { port: 5174, proxy },
  preview: { port: 5174, proxy },
})
```

### 📌 与 React 版的差异

**除了插件和端口，无差异。**

这是本阶段的**第一个结论**，而且它出现得比预想的早：

> **同域代理是构建工具的事，与前端框架完全无关。**
>
> `F-ADR-002`（httpOnly Cookie + 同域）这条影响深远的决策，
> 在换框架时的迁移成本是**零**。

---

## 五、⚠️ 容易写错的地方

### 1. 端口冲突

第一节第 2 问：**必须能同时开着**（`03-实施计划.md` 第 2 节建议左右对照开发）。

Vue 用 5174，React 保持 5173。⚠️ `preview` 也要改——React 版
`server` 和 `preview` 都是 5173，照抄会撞。

### 2. `main.ts` 的注册顺序

```ts
const app = createApp(App)
app.use(createPinia())        // ⚠️ 必须在 router 之前
app.use(router)
app.use(Antd)
app.mount('#app')
```

为什么 pinia 要在 router 之前：`vue-v0.5.0` 的导航守卫里要 `useAuthStore()`。
router 一旦 `use`，首次导航可能立刻触发守卫——那时 pinia 必须已经就绪。

⚠️ **这个 bug 在本 tag 不会暴露**（还没有守卫），到 `vue-v0.5.0` 才炸，
到时候报错是 `getActivePinia() was called with no active Pinia`，
**看起来像忘了装 pinia，实际是注册顺序问题**。现在就写对。

### 3. `client.ts` 直接复制，但**别急着加 store 相关的代码**

本 tag 的 `client.ts` 只要 `baseURL` + `withCredentials` + timeout。
CSRF 注入、401 分流、版本号感知分别属于 `vue-v0.2.0` / `vue-v0.12.0` / `vue-v0.11.0`。

> **严禁提前实现后续 tag 的功能**（根 `CLAUDE.md` 第 0 节）。
> 你已经知道 React 版最终长什么样了——**这让「提前实现」的诱惑在本阶段格外大**。
> 忍住。跨 tag 的 diff 是核心产物。

### 4. `withCredentials: true` 不能少

```ts
withCredentials: true,
// ⚠️ 忘了它的表现是「登录接口成功，之后所有请求 401」——
//    看起来像后端问题，实际是 Cookie 根本没发出去。
```

**这个坑与框架无关**，React 版注释里已经记过。照抄。

### 5. `.gitignore` 要加两条

```
frontend-vue/node_modules
frontend-vue/dist
```

⚠️ 检查一下 React 版当初是怎么写的——如果写的是 `frontend/dist`（带前缀），
那 `frontend-vue/dist` **不会**被它匹配到。

---

## 六、卡住了看这里

<details>
<summary><b>提示：main.ts</b></summary>

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())     // ⚠️ 顺序：pinia → router
app.use(router)
app.use(Antd)
app.mount('#app')
```
</details>

<details>
<summary><b>提示：最小 router</b></summary>

```ts
import { createRouter, createWebHistory } from 'vue-router'

// ⚠️ classic createRouter，不是 vue-router/auto（V-ADR-013）
export default createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', component: () => import('@/pages/Home.vue') }],
})
```
</details>

---

## 七、自测清单

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | `npm run dev` | :5174 起来，页面可见 |
| 2 | React 版 `npm run dev` 同时开着 | :5173 不受影响 |
| 3 | 浏览器访问 `http://localhost:5174/api/v1/health/` | 返回后端 JSON（代理生效） |
| 4 | `npm run typecheck` | 通过 |
| 5 | `npm run build` | 通过 |
| 6 | `git status` | `dist/`、`node_modules/` 不出现 |
| 7 | 后端 `pytest -q` | **417 全绿** |
| 8 | React 版 `cd frontend && npm run test` | **98 全绿** |

⚠️ 用例 7、8 每个 tag 都要跑（`03-实施计划.md` 第 4 节）。

---

## 八、和我的实现对比什么

```bash
diff -u frontend/vite.config.ts frontend-vue/vite.config.ts
diff -u frontend/src/api/client.ts frontend-vue/src/api/client.ts
```

| 对比点 | 想一想 |
| --- | --- |
| `vite.config.ts` 的差异有几行 | 超过 5 行的话，你改了什么不该改的？ |
| `changeOrigin` 设了 false 吗 | 设成 true 试试，看 `vue-v0.2.0` 的登录会怎么失败 |
| 有没有顺手改后端 | 改了就说明对「适配层已经做完了」这件事还没信 |
| 有没有提前写 CSRF / 401 | 写了的话 `vue-v0.2.0` 的 diff 就讲不清一件事了 |

---

## 九、📌 与 React 版的差异

| 项 | 差异 |
| --- | --- |
| `vite.config.ts` | 🟢 **仅插件与端口** |
| `client.ts` | 🟢 **无差异**（逐字复制） |
| `.gitignore` / `README` | 🟢 无差异（只是多一份） |
| `main.ts` vs `main.tsx` | 🟡 同构：`createApp().use()` ↔ `createRoot().render()` |
| 类型检查 | 🟡 `vue-tsc` ← `tsc` |
| **后端改动** | 🟢 **0**（React 阶段是 `fe-v0.2.0` 整整一个 tag） |

**本 tag 的结论**：骨架层几乎完全与框架无关。

---

## 十、延伸思考

1. `fe-v0.1.0` 当时要同时处理「同域代理」和「说服自己不要用 localStorage 存 token」。
   本 tag 只剩前者——**后者的成果被直接继承了**。
   在你自己的项目里，有哪些决策具备这种「一次决定，后续免费」的性质？

2. 现在有两个 Vite 配置几乎一样。**要不要抽成共享配置？**
   先看 [V-ADR-001](../02-设计文档.md) 再回答——
   这个问题的答案在**本项目**和在**普通项目**里是相反的。

3. 试着把 `changeOrigin` 改成 `true`，然后跳到 `vue-v0.2.0` 做一次登录。
   **报错信息会指向真正的原因吗？** 这类「报错指不到原因」的坑，
   有没有共同特征？
