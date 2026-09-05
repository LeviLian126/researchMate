# LLM Wiki 增量知识编译改造 Plan

## 1. 目标与边界

将当前：

```text
Document
→ Chunks
→ 分组生成 WikiPage
→ append
```

改为：

```text
Document
→ Knowledge Delta
→ Existing Wiki
→ Merge / Update
→ Canonical Wiki
```

核心目标：

- Wiki 是持续演化的全局知识层，不是文档摘要集合。
- Chunk 只作为局部分析和 provenance 单元。
- 新文档优先补充已有 Wiki，而不是重复创建页面。
- Wiki 保留全文级结构、实体关系和来源追踪。
- Query 默认 Wiki-first，Raw RAG 仅作为 fallback。

本阶段不做：

- 完整知识图数据库；
- Query answer 自动写回 Wiki；
- 跨项目 Wiki；
- Wiki embedding / 独立 Qdrant index；
- Raw chunking 改造。

---

# 2. Wiki 编译流程

## 2.1 新文档局部抽取

Raw Chunks 按 token budget 分组。

每组不直接生成最终 WikiPage，而是生成：

```text
KnowledgeFragment
- entities
- claims
- relations
- section context
- source_chunk_ids
```

---

## 2.2 文档级 Reduce

将同一文档的 fragments 归并为：

```text
DocumentKnowledgeDelta
```

完成：

- 同义实体归一；
- 跨 chunk claim 合并；
- 关系补全；
- 文档主题、结构、结论提炼；
- provenance 合并。

长文档采用层次化 Reduce：

```text
Chunk
→ Section Knowledge
→ Document Knowledge
```

避免简单抽样或局部摘要拼接。

---

## 2.3 与 Existing Wiki 对齐

使用新 `DocumentKnowledgeDelta` 检索现有 Wiki，判断每项知识属于：

```text
CREATE
UPDATE
LINK
CONFLICT
```

典型流程：

```text
New Knowledge
    ↓
搜索现有 Wiki title / alias / BM25 candidate
    ↓
Canonical Resolution
    ↓
Mutation Plan
```

同一概念应更新已有 canonical page，不创建重复页面。

例如：

```text
Hybrid Search
Hybrid Retrieval
Qdrant Hybrid Search
```

最终归并到同一 WikiPage。

---

## 2.4 增量更新 Wiki

只更新受影响页面：

```text
Existing Wiki
+
Knowledge Delta
→ Updated Wiki
```

不要每次新文档都重新生成整个 Wiki。

更新后同步：

- page content / summary；
- aliases；
- relations / wikilinks；
- source provenance；
- document overview；
- wiki generation version。

---

## 2.5 Conflict 处理

新知识与已有知识冲突时：

- 不直接覆盖旧事实；
- 保留双方 provenance；
- 让最终 Wiki 表达版本、条件或来源差异。

Raw source 始终是 source of truth。

---

# 3. 数据结构调整

## `wiki_knowledge.py`

新增 ingestion 中间模型：

```text
KnowledgeFragment
KnowledgeEntity
KnowledgeClaim
KnowledgeRelation
DocumentKnowledgeDelta
WikiMutation
```

---

## `WikiPage`

保持现有主体结构，补充支持增量知识维护所需字段。

建议 Wiki 内部逐步从：

```text
content: str
```

升级为：

```text
claims[]
summary
aliases
links
source_chunk_ids
```

`content` 作为最终渲染结果，而不是唯一知识源。

---

# 4. 文件级修改

## `services/wiki_compiler.py`

改为 Wiki 编译 orchestrator：

```text
compile_index()
→ extract fragments
→ reduce document knowledge
→ resolve existing wiki
→ plan mutations
→ synthesize affected pages
```

不再让每个 chunk group 直接生成最终 WikiPage。

---

## 新增 `services/wiki_knowledge.py`

负责：

- KnowledgeFragment schema；
- DocumentKnowledgeDelta；
- canonical entity / claim model；
- WikiMutation model。

---

## 新增 `services/wiki_merge.py`

负责：

```text
New Knowledge
+
Existing Wiki
→ Mutation Plan
```

包括：

- canonical resolution；
- CREATE / UPDATE / LINK / CONFLICT；
- provenance merge。

---

## `ingestion_service.py`

Wiki ingestion 调整为：

```text
parse
→ raw chunks
→ raw index
→ compile Knowledge Delta
→ load related existing Wiki
→ apply mutations
→ persist Wiki
→ mark wiki fresh
```

Wiki 更新失败时：

- Raw ingestion 仍成功；
- Wiki 标记 stale；
- Query 自动 fallback Raw RAG。

---

## Wiki Store

需要支持：

- 查询项目现有 WikiPage；
- 根据 title / alias 找候选；
- 批量 create / update affected pages；
- Wiki generation 更新。

避免每次全量覆盖 Wiki。

---

# 5. 与 Query 路径衔接

保持前面确定的三级查询：

```text
Tier 1
Wiki → Answer

Tier 2
Wiki → source_chunk_ids → Raw Evidence → Answer

Tier 3
Full RAG
```

只有：

```text
wiki_generation == knowledge_generation
```

时允许 Wiki-first short circuit。

Wiki stale 时直接走 Raw fallback。

---

# 6. 验收标准

## 全局理解

同一概念分散在文档多个位置时：

```text
最终只能有一个 canonical WikiPage
```

且页面能够综合全文信息，而非局部摘要拼接。

---

## 增量更新

已有 10 篇文档生成 Wiki 后新增 2 篇：

- 已有概念应 UPDATE；
- 新概念才 CREATE；
- 新关系可以 LINK；
- 冲突知识进入 CONFLICT；
- 不重新编译无关 WikiPage。

---

## Provenance

更新后的 WikiPage 必须能追溯：

```text
Wiki
→ claim / page
→ source_chunk_ids
→ Raw Document
```

---

## Freshness

Wiki 更新成功：

```text
wiki_generation == knowledge_generation
```

更新失败：

```text
wiki_generation < knowledge_generation
```

Query 不允许使用 stale Wiki 直接回答。

---

# 7. 测试

重点补充四类测试。

### `test_wiki_fragment_extraction.py`

验证局部知识抽取和 provenance。

### `test_wiki_document_reduce.py`

验证：

- 跨 chunk entity merge；
- relation merge；
- document-level summary / argument flow。

### `test_wiki_incremental_merge.py`

构造：

```text
Existing Wiki
+
New Document Delta
```

验证：

- UPDATE；
- CREATE；
- LINK；
- CONFLICT；
- alias merge；
- provenance merge。

### `test_wiki_ingestion_integration.py`

场景：

```text
前 10 篇文档
→ Existing Wiki

新增第 11 / 12 篇
→ 增量更新
```

验证：

- 只更新相关页面；
- 无重复 canonical page；
- Wiki generation 正确推进；
- Wiki failure 不影响 Raw ingestion。

---

# 8. 最终架构

```text
Raw Document
    ↓
Chunks
    ↓
Local Knowledge Extraction
    ↓
Document-level Reduce
    ↓
DocumentKnowledgeDelta
    ↓
Search Existing Wiki
    ↓
Canonical Resolution
    ↓
CREATE / UPDATE / LINK / CONFLICT
    ↓
Canonical Persistent Wiki
    ↓
Wiki-first Query
```

核心原则：

> 新文档不生成“另一套 Wiki”，而是生成对现有 Wiki 的 Knowledge Delta。

最终关系应满足：

```text
Wiki(t+1)
=
Wiki(t)
+
KnowledgeDelta(new documents)
```

而不是：

```text
Wiki
=
Summary(Document1)
+
Summary(Document2)
+
...
```