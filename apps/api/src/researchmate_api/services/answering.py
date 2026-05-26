from uuid import uuid4

from researchmate_api.schemas.common import Citation, SourceMode, SourceSummary, SourceType
from researchmate_api.services.retrieval import snippet
from researchmate_api.services.store import ChunkEntry


# 根据本地 chunk 生成可溯源回答，不调用真实 LLM。
def build_grounded_answer(query: str, mode: SourceMode, chunks: list[ChunkEntry]) -> tuple[str, list[Citation], SourceSummary]:
    citations: list[Citation] = []
    for index, chunk in enumerate(chunks, start=1):
        citations.append(
            Citation(
                id=uuid4(),
                source_type=chunk.source_type,
                document_id=chunk.document_id,
                chunk_id=chunk.id,
                page_no=chunk.page_no,
                slide_no=chunk.slide_no,
                url=chunk.url,
                quote=snippet(chunk.text),
                claim_id=f"claim_{index}",
            )
        )
    if not citations:
        return (
            "资料中未找到足够依据，因此我不会编造答案。请先上传并完成解析，或切换到 Web/Hybrid 模式。",
            [],
            SourceSummary(local_chunks=0, web_pages=0),
        )
    bullets = [f"{index}. {citation.quote}" for index, citation in enumerate(citations, start=1)]
    answer = (
        f"针对问题“{query}”，我优先依据已上传资料回答：\n"
        + "\n".join(bullets)
        + "\n\n结论只来自 Sources 中列出的片段；如需最新外部资料，请使用 /search 或 /hybrid。"
    )
    summary = SourceSummary(
        local_chunks=sum(1 for item in citations if item.source_type == SourceType.LOCAL_DOC),
        web_pages=sum(1 for item in citations if item.source_type == SourceType.WEB_PAGE),
    )
    return answer, citations, summary


# 生成本地开发用 Web evidence，占位生产 provider。
def build_demo_web_evidence(query: str) -> ChunkEntry:
    return ChunkEntry(
        id=uuid4(),
        user_id=uuid4(),
        project_id=uuid4(),
        document_id=None,
        source_type=SourceType.WEB_PAGE,
        source_title="Demo web provider",
        text=(
            "Web provider adapter is wired but no live SERPER/JINA/FIRECRAWL key is used in this local run. "
            f"Query summary: {query}. Configure provider API keys in backend env for real search and crawl."
        ),
        url="https://example.com/researchmate/configure-web-provider",
    )
