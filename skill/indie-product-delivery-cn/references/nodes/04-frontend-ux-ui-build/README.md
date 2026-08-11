# Frontend 构建

构建一个真实、有韧性的用户界面，使其状态、交互、无障碍、布局和集成行为与真实数据和失败条件保持一致。
把视觉质量和实现质量视为同一个产品边界：一个带有虚构数据、状态归属混乱、隐藏溢出或不诚实 fallback 的精致屏幕并不完整。

根据已变更的旅程选择相关关注点，而不是把每一个模式都套用到每一个组件上。

| 实现面 | 期望属性 |
|---|---|
| 状态与数据流 | 单一数据源、显式的 loading/empty/error/success 状态、不虚构成功 |
| 组件归属 | 内聚的组件和 hooks、稳定契约、无跨层重复策略 |
| 交互 | 键盘、指针、焦点、重复操作、取消和清理行为可预测 |
| 响应式布局 | 内容和控件始终可达，无重叠、裁剪或意外的滚动陷阱 |
| 性能与生命周期 | 有界渲染与请求、清理 listeners/observers、无可避免的 rerender 循环 |
| AI 生成代码风险 | 确认组件/库 API、移除占位 UI 和示例数据、避免 cargo-cult 抽象与仅测试行为 |

## 阅读相关工作流

| 需求 | 阅读 |
|---|---|
| 决定视觉方向、设计系统或参数 | `visual-direction-and-design-system.md` |
| 发布前检查已命名的反模式 | `anti-default-directives.md` |
| 恢复界面并设计其旅程、层级、内容和完整状态 | `experience-flow-content-and-states.md` |
| 实现组件、交互、无障碍、响应式、防重叠或性能 | `component-responsive-accessible-build.md` |
| 查找具体代码模式（技术栈 / 动画 / 字体 / 图标 / z-index） | `implementation-patterns.md` |
| 处理外部素材、审计现有工作或安全现代化 | `prototype-and-redesign.md` |
| 在浏览器中验证、调试渲染/集成失败或交接 | `browser-proof-and-debug.md` |
| 在前端界面中编写长篇帮助、说明或文档 | 默认运行 `humanizer` 技能 |
| 构建或刷新持久的 HTML 项目文档 | `../08-agent-context-html/README.md` |

## 输出契约

返回已变更的用户旅程和界面、相关内容和状态、响应式和无障碍行为、实际运行的视觉/浏览器验证、
持久文档影响，以及剩余的风险或缺口。说明该切片是 `BUILT`、`BUILT_WITH_NAMED_GAPS`、
`BLOCKED`，还是需要重新进入 Node02/03。
