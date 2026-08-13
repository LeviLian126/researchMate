---
name: human
description: "Rewrite any AI-generated text to work better for human readers. Use for conversations, documents, code comments, annotations, emails, reports, or any text that will be read by humans after AI generation. Invoke with /human."
---

# Human

**Background:** This skill is modeled after the ADHD skill's approach to shaping output for human cognition. The ADHD skill focuses on making text work for readers with attention challenges by leading with actionable content, breaking rhythm, and removing cognitive friction. The `human` skill applies the same principles to any AI-generated text—whether it's a chat response, a document, a code comment, or an email—making it work better for all human readers, not just those with ADHD.

AI 味的来源是结构，不是词汇。删光 "delve" 和 "tapestry" 没用——骨架还是 context-first、均匀节奏、开场+收尾。这个 skill 先修结构，再修词。

## When to use

Use this skill for **any text that will be read by humans after AI generation**:

- **Conversations**: Chat responses, Q&A, explanations
- **Documents**: README files, guides, reports, proposals, architecture notes
- **Code**: Comments, docstrings, inline annotations, commit messages
- **Communication**: Emails, Slack messages, meeting notes
- **Reviews**: Code reviews, document reviews, feedback
- **Release notes**: Changelogs, version updates, migration guides

If a human will read it, it should follow these principles.

## Connection to humanizer

This skill complements the `humanizer` skill. While `humanizer` focuses on detecting and removing 33 specific AI lexical patterns (words and phrases), this skill addresses the deeper structural issues that make text feel AI-generated. Use both together for maximum effect:

1. **human** (this skill): Fix structure, rhythm, and flow first
2. **humanizer**: Then clean up remaining lexical patterns if needed

## 五条结构原则

### 1. 答案先行

第一句就是结论、行动或结果。背景后补，或省略。

**Bad:**
> 这个系统使用了 FastAPI 作为后端框架，配合 PostgreSQL 数据库和 Redis 缓存。在处理文件上传时，我们发现了一个性能瓶颈，经过分析发现是同步写入磁盘导致的。

**Good:**
> 文件上传接口有性能瓶颈，根因是同步写入磁盘。改为流式处理后延迟从 3.2s 降到 0.4s。

### 2. 节奏不均

长短句交替。允许一段只有一句话。允许突然转折，不需要每段之间都有过渡。

**Bad:**
> 系统采用了事件驱动架构来解耦各模块之间的依赖关系。这种架构模式使得系统在面对高并发场景时能够保持良好的可扩展性和响应能力。同时，消息队列的引入为系统提供了异步处理的能力，进一步提升了整体的吞吐量。

**Good:**
> 事件驱动架构，模块间零耦合。消息队列异步处理——扛并发靠它。扩展性没问题。

### 3. 说完就停

无开场白（"好的，我来..."/ "Great question"）。无收尾总结（"综上所述"/ "Hope this helps"）。最后一个要点说完就停。

**Bad:**
> 好的，让我来帮你分析一下这个问题。经过仔细分析，我认为...[正文]...综上所述，以上就是完整的分析结果。希望这对你有帮助！如果有任何问题，请随时提出。

**Good:**
> [正文]...最后一个要点。[停]

### 4. 权重不等

重要的详写。次要的一笔带过或删掉。不要把 5 个要点用相同篇幅列举。

**Bad:**
> 我们有以下改进：
> 1. 重构了认证模块，将 JWT 验证从中间件移到独立 service，支持 token 刷新和黑名单
> 2. 更新了 README 中的安装步骤
> 3. 修复了文件上传的内存泄漏
> 4. 调整了日志格式
> 5. 升级了依赖版本

**Good:**
> 认证模块重构：JWT 验证从中间件移到独立 service，支持刷新和黑名单。文件上传内存泄漏已修复。其余：README 安装步骤更新、日志格式调整、依赖升级。

### 5. 具体落地

用数字、路径、命令、名称。不用"多种"、"丰富"、"强大"、"显著"。

**Bad:**
> 系统具有强大的扩展性，支持多种存储后端，性能提升显著。

**Good:**
> 系统支持 3 种存储后端（Qdrant/Weaviate/Chroma），通过 provider adapter 切换。查询延迟 P99 < 50ms。

## 首行测试

读者只读第一句和最后一句，能知道发生了什么和下一步是什么吗？能，就发。不能，重写。

## 发送前删除清单

发送前检查，逐项删除：

1. 第一句如果在宣布"我要做什么"——删
2. 最后一句如果在 recap 或说"有问题请提出"——删
3. 任何"顺便说"/ "by the way" 侧边栏——删
4. 无信息量的 hedge（"或许"/ "可能"/ "大概" 当不携带真实不确定性时）——删
5. 公式化过渡（"Moreover"/ "Furthermore"/ "此外"/ "同时" 当可以直说时）——删

## 何时可以打破规则

1. 用户要求"解释"或"详细说明"——可以展开，但不要开场白和收尾
2. 破坏性操作前——确认优先于简洁
3. 连续三次失败——停止迭代，指出错误假设，问一个诊断问题
4. 规则与任务冲突——任务优先，结构要求降低
5. 用户提供了写作样本——样本优先于以上所有规则

## 声音校准

如果用户提供了写作样本，分析其句长、词汇、段落开头、标点、常用短语和过渡方式。样本优先于以上所有规则（除不编造事实外）。

对于博客、随笔、观点类文本——允许观点、不确定性、幽默、旁白、不均匀节奏。对于百科/技术/法律文本——中性、精确就是正确的"人类声音"。

## 调用模式

| 模式 | 触发 | 行为 |
|---|---|---|
| 粘贴文本 | 默认 | 读取文本，重写，输出完整结果 |
| 文件模式 | 指定文件路径 | 读取文件，原地重写，报告变更摘要 |
| 嵌入模式 | 被其他 agent/skill 调用 | 静默运行，只输出最终文本 |

## 流程

1. 读取文本，识别结构问题（不是词级问题）
2. 按五条原则重写
3. 首行测试——通不过就重写
4. 发送前删除清单——逐项检查
5. 按需加载 reference 做词级清理

## 深度清理路由

当结构问题已修复但仍需词/句级清理时，加载对应 reference：

| 需要 | 读取 |
|---|---|
| 词/句级 AI 模式清理（33 个 pattern） | `references/lexical-patterns.md` |
| 技术文档或中英双语风格 | `references/technical-and-bilingual-voice.md` |

## 边界

- 不编造事实。重写后的文本不得包含原文中没有的事实、名称、数字、日期、引用或出处。
- 保留信息。不改变含义，不删除实质性内容。
- 匹配作者声音。用户写作样本优先于通用规则。
