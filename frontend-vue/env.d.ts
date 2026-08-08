/// <reference types="vite/client" />

// ⚠️ React 版不需要这个文件：.tsx 本来就是 TS 能理解的模块。
//    .vue 不是——没有这段声明，`import App from './App.vue'` 会报
//    「找不到模块或其相应的类型声明」。
//
//    vue-tsc 自己知道怎么处理 SFC，但 tsc 的语言服务（编辑器提示）需要它。
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, unknown>
  export default component
}
