# 实现模式

> **目标：** 为技术栈默认值、动画、字体、图标、依赖项、RSC 安全性、布局机制、z-index 层级与
> overscroll 隔离提供可直接使用的代码模式。
>
> **负责：** 具体代码模式与导入路径
>
> **不负责：** 架构决策（`component-responsive-accessible-build.md`）、方向决策（`visual-direction-and-design-system.md`）

这是编写前端代码的参考。本节点中的其他文件引用这些模式而不是重复它们。

## 技术栈默认值

除非设计解读选择了真正的设计系统，否则使用以下默认值：

- **框架：** React 或 Next.js。默认使用 Server Components (RSC)。
- **样式：** Tailwind v4（默认）。仅在现有项目需要时使用 Tailwind v3。
  - 对于 v4：不要在 `postcss.config.js` 中使用 `tailwindcss` 插件。使用 `@tailwindcss/postcss` 或
    Vite 插件。
- **动画：** Motion（前身为 Framer Motion 的库）。从 `motion/react` 导入：
  ```js
  import { motion } from "motion/react";
  ```
  `framer-motion` 包仍可作为旧版别名使用 - 新代码中优先使用 `motion/react`。

## 动画模式

### 连续值：使用 Motion，不要用 useState

永远不要使用 `useState` 来跟踪由用户输入驱动的连续值（鼠标位置、滚动进度、指针物理、磁吸悬停）。
`useState` 在每次变化时重新渲染 React 树，并在移动端崩溃。

```js
// 正确：用 Motion 值跟踪连续变化
import { useMotionValue, useTransform, useScroll } from "motion/react";

const x = useMotionValue(0);
const opacity = useTransform(x, [0, 100], [1, 0]);
const { scrollYProgress } = useScroll();
```

### 仅使用 GPU 友好的属性

只动画化 `transform` 和 `opacity`。永远不要动画化 `top`、`left`、`width`、`height`、`margin` 或
`padding` - 这些会触发布局重计算并导致卡顿。

```css
/* 正确 */
transition: transform 200ms ease, opacity 200ms ease;
transform: translateY(0);

/* 错误 */
transition: top 200ms ease, height 200ms ease;
```

### 滚动监听：IntersectionObserver 或 CSS，不要用 window.addEventListener

```js
// 正确：IntersectionObserver
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
    }
  });
}, { threshold: 0.1 });

// 正确：CSS 滚动驱动动画（现代浏览器）
@keyframes reveal {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
animation: reveal linear;
animation-timeline: view();
animation-range: entry 0% entry 100%;

// 错误：永远不要这样做
window.addEventListener("scroll", handleScroll); // 会导致卡顿
```

### 减少动效回退

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### 清理

始终在 `useEffect` 中清理事件监听器、观察器、动画实例和计划任务：

```js
useEffect(() => {
  const observer = new IntersectionObserver(callback);
  observer.observe(ref.current);
  return () => observer.disconnect();
}, []);
```

## 字体策略

### 加载方式

- **Next.js：** 使用 `next/font`：
  ```js
  import { Geist, Geist_Mono } from "next/font/google";
  const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });
  const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });
  ```
- **其他框架：** 使用 `@font-face` + `font-display: swap` 自托管：
  ```css
  @font-face {
    font-family: "Geist";
    src: url("/fonts/Geist.woff2") format("woff2");
    font-display: swap;
    font-weight: 100 900;
  }
  ```

**永远不要在生产环境中通过 `<link>` 引用 Google Fonts。** 这会导致渲染阻塞请求并
将用户 IP 暴露给 Google。

### 字体搭配

| Sans | Mono | 使用场景 |
|---|---|---|
| Geist | Geist Mono | 默认现代 SaaS / AI 营销 |
| Satoshi | JetBrains Mono | 简洁产品 UI |
| Cabinet Grotesk | Inter Tight | 创意 / 代理商 |
| GT America | IBM Plex Mono | 企业 / 技术型 |

### 默认展示类型

```css
/* 展示 / 标题 */
text-4xl md:text-6xl tracking-tighter leading-none;

/* 正文 / 段落 */
text-base text-gray-600 leading-relaxed max-w-[65ch];
```

## 图标策略

- **优先顺序：** `@phosphor-icons/react`、`hugeicons-react`、`@radix-ui/react-icons`、
  `@tabler/icons-react`。
- **不推荐：** `lucide-react`。仅在用户明确要求或项目已依赖它时可接受。
- **永远不要手绘 SVG 图标。** 如果缺少某个字形，安装第二个库或从基础元素组合 - 不要从头绘制
  图标路径。
- **每个项目一个图标族。** 不要在同一组件树中混用 Phosphor 和 Lucide。
- **全局统一 `strokeWidth`**（例如 `1.5` 或 `2.0`）。

## 依赖验证

导入任何第三方库之前，检查 `package.json`。如果缺少该包，先输出安装命令。**永远不要假设某个库已存在。**

```bash
# 导入前检查
grep "motion" package.json
# 如果缺失：
npm install motion
```

## RSC 安全性

- 全局状态仅在 Client Components 中工作。在 Next.js 中，将 provider 包裹在 `"use client"` 组件中。
- 任何使用 Motion、滚动监听或指针物理的组件必须是带有 `'use client'` 的隔离叶子节点。
  Server Components 仅渲染静态布局。
- Server Components 可以将可序列化的 props 传递给 Client Components，但不能使用 hook、
  事件处理器或浏览器 API。

```jsx
// page.tsx（Server Component - 无 "use client"）
import { Hero } from "./Hero";

export default function Page() {
  return <Hero title="Welcome" />;
}

// Hero.tsx（Client Component - 交互式）
"use client";
import { motion } from "motion/react";

export function Hero({ title }) {
  return <motion.h1 initial={{ opacity: 0 }}>{title}</motion.h1>;
}
```

## 布局机制

- **全高区块：** `min-h-[100dvh]`，永远不要用 `h-screen`（iOS Safari 地址栏会导致布局跳动）。
- **多列布局：** CSS Grid，永远不要用 flexbox 百分比计算：
  ```jsx
  // 正确
  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

  // 错误
  <div className="flex">
    <div className="w-[calc(33%-1rem)]">
  ```
- **容器：** `max-w-[1400px] mx-auto` 或 `max-w-7xl`。
- **标准断点：** `sm 640`、`md 768`、`lg 1024`、`xl 1280`、`2xl 1536`。

## z-index 层级

使用分层 token 而不是裸值。将这些定义为 CSS 变量或 Tailwind 配置条目：

```css
:root {
  --z-base: 0;
  --z-dropdown: 10;
  --z-sticky: 20;
  --z-drawer: 30;
  --z-modal: 40;
  --z-toast: 50;
}
```

| 层 | Token | 用于 |
|---|---|---|
| base | `--z-base` (0) | 正常文档流 |
| dropdown | `--z-dropdown` (10) | 下拉选择菜单、自动补全、弹出框 |
| sticky | `--z-sticky` (20) | 固定头部、固定侧边栏、固定表头 |
| drawer | `--z-drawer` (30) | 滑出面板、导航抽屉 |
| modal | `--z-modal` (40) | 对话框、模态框、全屏覆盖层 |
| toast | `--z-toast` (50) | Toast 通知、snackbar、模态框上方的提示 |

规则：
- `z-index` 值必须来自 token 或 CSS 变量。永远不要内联 `z-index: 9999` 或类似的
  魔法数字。
- 如果出现堆叠冲突，添加一个 token 层而不是升级数字。
- 项目可以自定义层名称，但必须保持分层式的层级体系。

## Overscroll 隔离

防止滚动链（在模态框 / 抽屉内滚动传播到底层页面）：

```css
.modal-body {
  overscroll-behavior: contain;
  overflow-y: auto;
  max-height: 90vh;
}

/* 可选：模态框打开时锁定 body 滚动 */
body.modal-open {
  overflow: hidden;
  /* 保留滚动位置：使用 position: fixed 加 top 偏移量 */
}
```

对于保留滚动位置的 body 滚动锁定，在锁定前记录 `window.scrollY` 并在解锁时恢复。
仅使用 CSS 的 `body` 上 `overflow: hidden` 在某些浏览器中会跳到顶部。

---

**验收标准：** 阅读本文件后，你能够使用正确的 Motion 导入路径，用 `useMotionValue` / `useScroll`
代替 `useState` 编写动画，通过 `next/font` 或自托管 `@font-face` 加载字体，选择正确的图标库，
导入前验证依赖项，在 RSC 客户端叶子节点中隔离交互性，使用 CSS Grid 代替 flex 百分比计算，
使用 `min-h-[100dvh]` 代替 `h-screen`，使用分层 z-index token 代替魔法数字，并在模态框和抽屉上
应用 overscroll 隔离。
