import axios from 'axios'

/**
 * 统一的 API 客户端。
 *
 * baseURL 是相对路径 '/api/v1' 而不是绝对地址——这是 F-ADR-002 的直接结果：
 * 前端只对自己的源发请求，由 Vite（开发）/ Nginx（生产）转发到 Django。
 *
 * ⚠️ 本文件与 React 版（frontend/src/api/client.ts）**逐字相同**。
 *    axios 不认识 Vue 也不认识 React——这一层与框架无关。
 *
 * ⚠️ 现在它只有三行配置。CSRF 注入、401 分流、X-RBAC-Version 比对
 *    分别属于 vue-v0.2.0 / vue-v0.12.0 / vue-v0.11.0。
 *
 *    **不要提前写。** 你已经知道 React 版最终长什么样了，
 *    这让「提前实现」的诱惑在本阶段格外大——但跨 tag 的 diff 是核心产物
 *    （根 CLAUDE.md 第 0 节）。
 */
export const client = axios.create({
  baseURL: '/api/v1',
  // ⚠️ 不能少。同域下浏览器本会带 Cookie，但 axios 的 XHR 需要显式开启。
  //    忘了它的表现是「登录接口成功，之后所有请求 401」——
  //    看起来像后端问题，实际是 Cookie 根本没发出去。
  withCredentials: true,
  timeout: 15_000,
})
