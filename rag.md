# ResearchMate Hybrid RAG 架构设计与迭代计划

> 创建日期：2026-08-09
> 范围：写入端（文件解析 → chunking → 向量索引）+ 读取端（检索 → rerank → 生成）
> 目标：将当前"基础 Hybrid RAG"升级为"高质量 Hybrid RAG"，不做 Agentic RAG

---

## 1. 现状分析

### 1.1 完整数据流

```
┌──────────────────── 写入端（文件上传 → 索引） ────────────────────┐
│                                                                    │
│  PDF/DOCX/PPTX                                                     │
│    ↓                                                               │
│  DoclingDocumentParser.parse()                                     │
│    ├─ pypdf 后端: 逐页提取纯文本, 保留 page_no                     │
│    ├─ docling 后端: OCR + layout + table, 保留 page_no + anchors   │
│    ├─ DOCX: zipfile+xml.etree, 按段落, 识别 heading → section_title│
│    └─ PPTX: zipfile+xml.etree, 按 slide, 首行 → section_title      │
│    ↓                                                               │
│  ParsedBlock[] (text, page_no, slide_no, section_title, metadata)  │
│    metadata 含: parser_name, source_item_ref, source_anchors, bbox │
│    ↓                                                               │
│  build_projections()                                                │
│    ├─ PageProjection: 保留全部元数据 (section_title, anchors, bbox) │
│    └─ ChunkEntry: 只保留 page_no, slide_no, source_title(=filename)│
│       ⚠️ section_title 在此丢失                                     │
│       ⚠️ metadata(anchors, bbox, parser_info) 在此丢失              │
│    ↓                                                               │
│  chunk_text_for_index(target=900)                                   │
│    按 \n 切分, 累积到 900 字符                                     │
│    ⚠️ 无 overlap                                                   │
│    ⚠️ 超长段落不截断, 整体放入新 chunk (可能 > 900)                │
│    ⚠️ 不考虑语义边界                                               │
│    ↓                                                               │
│  Embedding: NVIDIA nv-embed-v1, 4096d, query/passage 区分          │
│  Sparse: SHA-256 token hash → 确定性稀疏向量 (非学习型)             │
│    ↓                                                               │
│  Qdrant upsert: {dense: 4096d, sparse: hash, payload: chunk_meta}  │
│  PostgreSQL chunks 表: id, text, page_no, slide_no, source_title   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────── 读取端（Ask 检索 → 生成） ────────────────────┐
│                                                                    │
│  POST /api/v1/ask {project_id, message, web_enabled}                │
│    ↓                                                               │
│  IdempotencyCoordinator.begin()                                    │
│    ↓                                                               │
│  GroundedQueryService.execute()                                    │
│    ↓                                                               │
│  ┌─ conversation context 注入 (query_context.py)                  │
│  │  滚动摘要 + 最近 N 条消息                                       │
│  │                                                                 │
│  ├─ 通道 1: BM25 应用层检索 (retrieval.py:45-88)                   │
│  │  tokenize: 拉丁词 + CJK 单字 + CJK bigram                       │
│  │  精确匹配奖励 +4.0, 标题匹配奖励 +0.75/token                   │
│  │  限制: 30 候选                                                  │
│  │                                                                 │
│  ├─ 通道 2: Dense 向量检索 (qdrant_store.py:132-158)              │
│  │  NVIDIA nv-embed-v1, 4096d, query input type                   │
│  │  限制: 30 候选                                                  │
│  │                                                                 │
│  ├─ RRF 融合 (retrieval.py:91-125, k=60, limit=50)                │
│  │  score = 1/(60+rank_lexical) + 1/(60+rank_semantic)            │
│  │                                                                 │
│  ├─ Tavily Web 搜索 (可选, 5 results, score=1/(60+n))             │
│  │                                                                 │
│  ├─ Cross-encoder Rerank (rerank.py)                              │
│  │  三级降级: qdrant native → nvidia → deterministic              │
│  │  Web 候选跳过 qdrant reranker                                  │
│  │                                                                 │
│  ├─ Token 预算裁剪 (pack_chunks, budget=8000)                    │
│  │                                                                 │
│  └─ LLM 生成 (answering.py:100-185)                               │
│     结构化 JSON: {answer, claims[{evidence_id, quote, ...}]}     │
│     schema 校验失败自动 repair (1 次重试)                          │
│     无证据时走 build_llm_chat_answer() (纯聊天)                   │
│                                                                    │
│  → Citation 映射回 page_no/slide_no/url                           │
│  → 写入 runs + messages + traces                                   │
└────────────────────────────────────────────────────────────────────┘
```

### 1.2 关键文件索引

| 组件 | 文件 | 行号 | 职责 |
|------|------|------|------|
| **写入端** | | | |
| 文档解析 | `workers/ai-worker/src/researchmate_worker/parsing.py` | 243-336 | Docling/pypdf 解析路由 |
| PDF 轻量解析 | 同上 | 40-82 | pypdf 逐页提取 |
| DOCX 解析 | 同上 | 151-185 | zipfile+xml.etree 按段落 |
| PPTX 解析 | 同上 | 187-241 | zipfile+xml.etree 按 slide |
| Chunk 切分 | `workers/ai-worker/src/researchmate_worker/jobs.py` | 7-23 | 固定 900 字符, 无 overlap |
| 投影构建 | `workers/ai-worker/src/researchmate_worker/ingestion_projections.py` | 15-69 | ParsedBlock → ChunkEntry |
| Embedding | `apps/api/src/researchmate_api/services/embedding.py` | 14-76 | NVIDIA nv-embed-v1 |
| Sparse 向量 | `apps/api/src/researchmate_api/services/qdrant_store.py` | 32-45 | SHA-256 hash 稀疏向量 |
| Qdrant 写入 | 同上 | 226-283 | upsert dense+sparse+payload |
| ChunkEntry 模型 | `apps/api/src/researchmate_api/services/_store_models.py` | 35-48 | dataclass 定义 |
| **读取端** | | | |
| Ask 端点 | `apps/api/src/researchmate_api/routers/ask.py` | 29-66 | HTTP 入口 |
| 编排核心 | `apps/api/src/researchmate_api/services/grounded_query.py` | 68-335 | retrieve→rerank→generate |
| 本地检索 | `apps/api/src/researchmate_api/services/query_retrieval.py` | 47-77 | BM25+Dense+RRF |
| BM25 | `apps/api/src/researchmate_api/services/retrieval.py` | 45-88 | 应用层 Python BM25 |
| RRF 融合 | 同上 | 91-125 | k=60 融合 |
| Tokenizer | 同上 | 15-24 | 拉丁词+CJK 单字+bigram |
| Dense 检索 | `apps/api/src/researchmate_api/services/qdrant_store.py` | 132-158 | Qdrant dense 查询 |
| Rerank | `apps/api/src/researchmate_api/services/rerank.py` | 全文件 | 三级降级 reranker |
| 生成 | `apps/api/src/researchmate_api/services/answering.py` | 100-185 | 结构化 JSON grounded answer |
| Token 裁剪 | `apps/api/src/researchmate_api/services/retrieval.py` | 128-130 | pack_chunks |

### 1.3 差距清单

| # | 差距 | 位置 | 影响 | 严重度 |
|---|------|------|------|--------|
| 1 | **Chunking 无 overlap** | `jobs.py:7-23` | chunk 边界上下文断裂，跨 chunk 的语义丢失 | 高 |
| 2 | **section_title 在 chunk 层丢失** | `ingestion_projections.py:49-68` | 检索时 LLM 不知道 chunk 属于哪个章节，无法利用文档结构 | 高 |
| 3 | **metadata(anchors, bbox) 在 chunk 层丢失** | 同上 | 无法做精准定位（如"第 3 页左上角"），citation 粒度只到 page | 中 |
| 4 | **Sparse 向量是 SHA-256 hash** | `qdrant_store.py:32-45` | 非学习型，无语义理解，"汽车"≠"轿车"，稀疏通道形同虚设 | 中 |
| 5 | **无 query rewriting** | `grounded_query.py:68-335` | 口语化/模糊问题检索质量差，无 HyDE/multi-query | 中 |
| 6 | **表格被当纯文本切分** | `jobs.py:7-23` | 表格行可能跨 chunk，行列关系断裂 | 中 |
| 7 | **RRF 权重均等** | `retrieval.py:91-125` | dense 和 BM25 权重相同，无法按场景调优 | 低 |
| 8 | **内存模式无向量检索** | `query_retrieval.py:47-77` | 本地开发只能测 BM25，无法测真实 hybrid | 低（设计取舍） |

---

## 2. 目标架构设计

### 2.1 设计原则

1. **结构感知**：chunk 保留 section 层级、page_no、position，让 LLM 知道"这段话来自哪个章节"
2. **语义连续**：overlap 保证 chunk 边界不丢上下文，跨 chunk 的引用不断裂
3. **学习型稀疏**：用真正的 sparse embedding 替代 hash，让稀疏通道有语义理解能力
4. **多粒度融合**：dense（语义）+ sparse（关键词）+ BM25（词频）三通道各有优势，加权融合
5. **Query 增强**：HyDE + multi-query 提升复杂问题的召回率

### 2.2 写入端目标架构

```
PDF/DOCX/PPTX
  ↓
DoclingDocumentParser (保持不变)
  ↓
ParsedBlock[] (text, page_no, slide_no, section_title, metadata)
  ↓
┌─────────────────────────────────────────────────────┐
│  Recursive Structure-Aware Chunker (新)              │
│                                                       │
│  Level 1: 按 section_title 边界分组                  │
│           每个 section 的 blocks 聚合为一个大文本块    │
│                                                       │
│  Level 2: section 内按段落 (\n\n) 切分               │
│           段落 < target_size → 整段保留              │
│           段落 > target_size → 进入 Level 3         │
│                                                       │
│  Level 3: 超长段落按句子 (。. ! ? \n) 切分           │
│           句子累积到 target_size 形成一个 chunk      │
│                                                       │
│  Overlap: 相邻 chunk 共享 prev_overlap 字符          │
│           target_size=1000, overlap=150 (15%)         │
│                                                       │
│  表格保护: 含表格标记的 block 整体保留不切分         │
│            超过 max_chunk_size 的表格单独成 chunk    │
│                                                       │
│  元数据传递:                                          │
│    section_title → ChunkEntry.section_title           │
│    section_path → ChunkEntry.parent_section_path      │
│      例: "第三章 系统设计 > 3.2 架构"                │
│    chunk_index → ChunkEntry.chunk_index (文档内序号) │
│    page_no → ChunkEntry.page_no (保持)               │
│    slide_no → ChunkEntry.slide_no (保持)             │
│    bbox → ChunkEntry.metadata (新增)                  │
└─────────────────────────────────────────────────────┘
  ↓
ChunkEntry[] (扩展字段)
  ↓
Embedding: NVIDIA nv-embed-v1 4096d (保持)
Sparse: BGE-M3 sparse 或 Qdrant 内置 BM25 (升级)
  ↓
Qdrant upsert: {dense, sparse/payload, payload: section_title + chunk_index + ...}
PostgreSQL chunks 表: 新增 section_title, chunk_index, parent_section_path 列
```

### 2.3 读取端目标架构

```
POST /api/v1/ask {project_id, message, web_enabled}
  ↓
IdempotencyCoordinator.begin()
  ↓
GroundedQueryService.execute()
  ↓
┌──────────────────────────────────────────────────────────────┐
│  Query Rewriting (新)                                          │
│                                                                │
│  Step 1: HyDE — LLM 生成假设性答案                             │
│    输入: 用户问题 + conversation context                      │
│    输出: 1 段假设性回答 (200-400 字)                           │
│    用途: 用假设答案做 dense 检索 (语义更接近目标 chunk)       │
│                                                                │
│  Step 2: Multi-Query — LLM 拆分问题                           │
│    输入: 用户问题                                              │
│    输出: 3 个检索变体 (不同措辞/角度)                         │
│    用途: 每个 variant 做一轮 BM25 + dense, 结果合并           │
│                                                                │
│  降级策略: LLM 不可用时直接用原始 query                        │
└──────────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────────┐
│  三通道检索 (升级)                                             │
│                                                                │
│  通道 1: BM25 (应用层, 保持)                                   │
│    输入: original_query + 3 variants                           │
│    每个查询取 30 候选, 合并后去重                              │
│    新增: section_title 匹配奖励 +1.5                           │
│                                                                │
│  通道 2: Dense (Qdrant, 升级)                                  │
│    输入: original_query + HyDE_answer                          │
│    original_query → 30 候选                                    │
│    HyDE_answer → 30 候选                                      │
│    合并去重                                                    │
│                                                                │
│  通道 3: Qdrant 内置 BM25 或 BGE-M3 sparse (升级)             │
│    替代 SHA-256 hash sparse                                   │
│    真正的稀疏语义匹配                                          │
└──────────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────────┐
│  加权 RRF 融合 (升级)                                          │
│                                                                │
│  weighted_score = w_dense * rrf(dense_rank)                    │
│                 + w_sparse * rrf(sparse_rank)                 │
│                 + w_bm25 * rrf(bm25_rank)                     │
│                                                                │
│  默认权重: w_dense=0.4, w_sparse=0.3, w_bm25=0.3              │
│  权重可通过 runtime_ai_config 动态调整                         │
│                                                                │
│  limit: 50 候选 (保持)                                         │
└──────────────────────────────────────────────────────────────┘
  ↓
Tavily Web 搜索 (保持, 可选)
  ↓
Cross-encoder Rerank (保持, 三级降级)
  ↓
Token 预算裁剪 (保持, 8000)
  ↓
LLM 生成 (保持, 结构化 JSON)
  ↓
Citation 映射 (升级: 可引用 section_title + page_no)
```

### 2.4 ChunkEntry 扩展

当前 `ChunkEntry` (`_store_models.py:35-48`)：

```python
@dataclass
class ChunkEntry:
    id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID | None
    source_type: SourceType
    source_title: str          # = filename
    text: str
    page_no: int | None = None
    slide_no: int | None = None
    url: str | None = None
    created_at: datetime = ...
```

目标扩展：

```python
@dataclass
class ChunkEntry:
    id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID | None
    source_type: SourceType
    source_title: str           # = filename
    text: str
    page_no: int | None = None
    slide_no: int | None = None
    url: str | None = None
    section_title: str | None = None          # 新增: 所属章节标题
    parent_section_path: str | None = None    # 新增: 章节路径 "第三章 > 3.2 架构"
    chunk_index: int = 0                      # 新增: 文档内序号
    char_start: int | None = None            # 新增: 在原文档的字符偏移
    char_end: int | None = None              # 新增: 结束偏移
    created_at: datetime = ...
```

---

## 3. 迭代计划

### Phase 1：Chunking 质量提升（写入端）

**目标**：chunk 保留文档结构，有 overlap，不硬切语义单元。

**改动文件**：

| 文件 | 改动 |
|------|------|
| `workers/ai-worker/src/researchmate_worker/jobs.py` | 重写 `chunk_text_for_index` → `chunk_recursive` |
| `workers/ai-worker/src/researchmate_worker/ingestion_projections.py` | 传递 section_title、section_path、chunk_index 到 ChunkEntry |
| `apps/api/src/researchmate_api/services/_store_models.py` | ChunkEntry 新增 5 个字段 |
| `apps/api/src/researchmate_api/persistence/_postgres_chunks.py` | chunks 表读写适配新字段 |
| `infra/supabase/migrations/` | 新 migration: `ALTER TABLE chunks ADD COLUMN section_title, parent_section_path, chunk_index, char_start, char_end` |
| `apps/api/src/researchmate_api/services/qdrant_store.py` | Qdrant payload 新增 section_title 等字段 |

**chunk_recursive 设计**：

```python
def chunk_recursive(
    blocks: list[ParsedBlock],
    *,
    target_size: int = 1000,
    overlap: int = 150,
    max_chunk_size: int = 2000,
) -> list[ChunkProjection]:
    """Split parsed blocks into overlapping, structure-aware chunks."""

    # 1. 按 section_title 分组 blocks
    #    无 section_title 的 block 归入前一个 section 或 "general"

    # 2. section 内按段落聚合
    #    段落 < target_size → 整段保留
    #    段落 > target_size → 按句子切分

    # 3. 句子切分规则
    #    中文: 按 。！？\n 切分
    #    英文: 按 . ! ? \n 切分

    # 4. Overlap
    #    相邻 chunk 共享前一个 chunk 的末尾 overlap 字符
    #    overlap 不跨 section 边界

    # 5. 表格保护
    #    metadata["source_label"] == "table" 的 block 整体保留
    #    超过 max_chunk_size 的表格单独成 chunk，不切分

    # 6. 输出
    #    ChunkProjection(text, section_title, parent_section_path,
    #                     chunk_index, char_start, char_end,
    #                     page_no, slide_no)
```

**验证**：
- 单元测试：构造 ParsedBlock 列表，验证 chunk 边界、overlap 长度、section 保留
- 对比测试：同一文档 before/after chunking，检查 chunk 数量和质量

---

### Phase 2：Sparse 向量升级（写入 + 读取端）

**目标**：用学习型 sparse embedding 替代 SHA-256 hash。

**方案选择**（二选一）：

**方案 A：Qdrant 内置 BM25 索引**（推荐，改动小）
- Qdrant 1.7+ 支持 `text-sparse` 字段类型，内置 BM25 稀疏索引
- 写入端：payload 里加 `text` 字段，Qdrant 自动建 BM25 索引
- 读取端：`query_dense` 改为 `query`（dense+sparse 联合检索）
- 不需要额外 embedding 模型

**方案 B：BGE-M3 多向量**（改动大但效果更好）
- BGE-M3 同时输出 dense(1024d) + sparse(学习型)
- 需要换 embedding 模型（从 NVIDIA 4096d → BGE-M3 1024d）
- 需要重建所有索引
- 影响面大

**推荐方案 A**，改动文件：

| 文件 | 改动 |
|------|------|
| `apps/api/src/researchmate_api/services/qdrant_store.py` | 删除 `sparse_text_vector`，改用 Qdrant payload text 索引 |
| `apps/api/src/researchmate_api/services/qdrant_store.py` | `upsert_chunks` 不再写 sparse vector，只写 dense + payload |
| `apps/api/src/researchmate_api/services/qdrant_store.py` | `query_dense` → `query_hybrid`，用 Qdrant `QueryRequest` 联合检索 |
| `apps/api/src/researchmate_api/services/query_retrieval.py` | 检索逻辑适配，sparse 通道从 Qdrant 取而非应用层 BM25 |

**验证**：
- 对比测试：同一查询，hash sparse vs Qdrant BM25 的召回质量
- 索引重建后全量验证

---

### Phase 3：Query Rewriting（读取端）

**目标**：对模糊/复杂问题提升召回率。

**改动文件**：

| 文件 | 改动 |
|------|------|
| `apps/api/src/researchmate_api/services/query_rewriting.py`（新） | HyDE + multi-query 实现 |
| `apps/api/src/researchmate_api/services/grounded_query.py` | 检索前插入 query rewriting 步骤 |
| `apps/api/src/researchmate_api/services/query_retrieval.py` | 检索适配多查询输入 |

**HyDE 实现**：

```python
def generate_hyde_answer(
    query: str,
    conversation_context: str,
    chat_provider: ChatProvider,
) -> str | None:
    """Generate a hypothetical answer for dense retrieval.

    Prompt: "Given this question and conversation context, write a brief
    factual answer (200-400 chars) as if you found the perfect source."
    """
    # LLM 不可用时返回 None, 检索降级为原始 query
```

**Multi-Query 实现**：

```python
def generate_query_variants(
    query: str,
    chat_provider: ChatProvider,
) -> list[str]:
    """Generate 3 retrieval variants from different angles.

    Prompt: "Rewrite this search query from 3 different angles:
    1. Same meaning, different words
    2. More specific
    3. Broader scope"
    """
    # LLM 不可用时返回 [query], 检索降级为单查询
```

**检索适配**：

```python
# query_retrieval.py 改造
def retrieve(self, ...):
    # Phase 3: query rewriting
    hyde_answer = generate_hyde_answer(query, context, chat_provider)
    variants = generate_query_variants(query, chat_provider)

    # BM25: 每个 variant 查一轮, 合并去重
    lexical = []
    for v in variants + [query]:
        lexical.extend(bm25_candidates(chunks, v, limit=30))
    lexical = deduplicate_by_chunk_id(lexical)

    # Dense: original_query + hyde_answer 各查一轮
    semantic = []
    semantic.extend(self._semantic_candidates(user, project_id, query))
    if hyde_answer:
        semantic.extend(self._semantic_candidates(user, project_id, hyde_answer))
    semantic = deduplicate_by_chunk_id(semantic)

    # 加权 RRF 融合
    candidates = fuse_candidates_weighted(
        lexical, semantic, sparse,
        weights=(0.3, 0.4, 0.3),
        limit=50,
    )
```

**验证**：
- 构造模糊/口语化测试问题，对比 before/after 召回质量
- LLM 降级测试：关闭 chat_provider，验证降级为原始检索

---

### Phase 4：加权 RRF + 检索质量评估

**目标**：可调权重融合 + 量化评估。

**改动文件**：

| 文件 | 改动 |
|------|------|
| `apps/api/src/researchmate_api/services/retrieval.py` | `fuse_candidates` → `fuse_candidates_weighted`，支持权重参数 |
| `apps/api/src/researchmate_api/persistence/_postgres_memory.py` | `runtime_ai_config` 新增检索权重配置 |
| `apps/api/src/researchmate_api/routers/` | 新增检索配置调优端点（可选） |

**加权 RRF**：

```python
def fuse_candidates_weighted(
    lexical: list[RetrievalCandidate],
    semantic: list[ChunkEntry],
    sparse: list[ChunkEntry] | None = None,
    *,
    weights: tuple[float, float, float] = (0.3, 0.4, 0.3),
    limit: int = 50,
    rrf_k: int = 60,
) -> list[RetrievalCandidate]:
    """Fuse three channels with configurable weights."""
    w_lexical, w_semantic, w_sparse = weights
    scores: defaultdict[UUID, float] = defaultdict(float)

    for candidate in lexical:
        rank = candidate.lexical_rank or 1
        scores[candidate.chunk.id] += w_lexical / (rrf_k + rank)

    for rank, chunk in enumerate(semantic, start=1):
        scores[chunk.id] += w_semantic / (rrf_k + rank)

    if sparse:
        for rank, chunk in enumerate(sparse, start=1):
            scores[chunk.id] += w_sparse / (rrf_k + rank)

    # ... 排序 + 截断
```

**评估数据集**（新建 `tests/fixtures/rag_eval/`）：

```
tests/fixtures/rag_eval/
  ├── documents/          # 5-10 个测试文档 (PDF/DOCX/PPTX)
  ├── queries.jsonl       # 20-30 个测试问题 + 期望召回的 chunk_id
  └── eval_runner.py      # 评估脚本: recall@k, mrr, ndcg
```

**评估指标**：
- **Recall@10**：前 10 个结果中包含正确答案的比例
- **MRR**（Mean Reciprocal Rank）：第一个正确结果的平均倒数排名
- **NDCG@10**：归一化折损累积增益

**验证**：
- Phase 1-3 完成后，跑评估数据集，对比 baseline 指标
- 调整权重，找最优配置

---

## 4. 实施顺序与依赖

```
Phase 1 (Chunking)          Phase 2 (Sparse)
     │                           │
     ↓                           ↓
     └───────┬───────────────────┘
             ↓
      Phase 3 (Query Rewriting)
             │
             ↓
      Phase 4 (加权 RRF + 评估)
```

- Phase 1 和 Phase 2 可以并行（一个改写入端 chunking，一个改 sparse 向量）
- Phase 3 依赖 Phase 1（chunk 质量不好时 query rewriting 效果有限）
- Phase 4 依赖 Phase 1-3（评估需要全部改造完成才有意义）

---

## 5. 不做的事项（明确排除）

| 事项 | 原因 |
|------|------|
| Agentic RAG（agent 循环、tool calls、multi-hop） | 用户明确要求不做，先实现 hybrid |
| Graph RAG（知识图谱检索） | 架构差异太大，不在 hybrid 范畴 |
| 换 embedding 模型（BGE-M3 dense） | NVIDIA nv-embed-v1 已满足需求，换模型影响面大 |
| 换 LLM 模型 | 当前 NVIDIA NIM 已满足需求 |
| 前端 UI 改造 | 本计划只改后端检索链路 |
| Postgres 模式的文件上传修复 | 单独处理（需要 S3 + Worker + Redis 配置） |

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| Phase 1 chunking 改动影响已有索引 | 需要重建索引（reindex），提供 reindex 脚本 |
| Phase 2 Qdrant BM25 需要 Qdrant 1.7+ | 检查当前 Qdrant 版本，必要时升级 |
| Phase 3 HyDE 增加 LLM 调用延迟 | HyDE 和 multi-query 并行调用；降级策略保证 LLM 不可用时不阻塞 |
| ChunkEntry 新增字段需要 DB migration | 新字段全部 nullable，向后兼容 |
| 评估数据集构建成本 | 先用 5 个文档 + 10 个问题做 MVP 评估 |
