from uuid import uuid4

from researchmate_api.schemas.common import Citation, Difficulty, SourceMode, SourceSummary
from researchmate_api.schemas.quiz import QuizQuestion, QuizSet
from researchmate_api.services.retrieval import snippet
from researchmate_api.services.store import ChunkEntry


# 基于本地 chunk 生成可溯源测验。
def generate_quiz_set(
    mode: SourceMode,
    chunks: list[ChunkEntry],
    citations: list[Citation],
    single_choice_count: int,
    short_answer_count: int,
) -> QuizSet:
    questions: list[QuizQuestion] = []
    citation_by_chunk = {citation.chunk_id: citation for citation in citations if citation.chunk_id}
    source_chunks = chunks or []
    total = max(1, single_choice_count + short_answer_count)
    for index in range(min(single_choice_count, len(source_chunks), total)):
        chunk = source_chunks[index % len(source_chunks)]
        quote = snippet(chunk.text, 180)
        citation = citation_by_chunk.get(chunk.id)
        questions.append(
            QuizQuestion(
                id=uuid4(),
                type="single_choice",
                question=f"根据资料片段，下列哪项最能概括第 {index + 1} 个知识点？",
                options=[
                    quote,
                    "与资料无关的泛化说法",
                    "没有来源支撑的最新网络结论",
                    "仅包含调试或内部 trace 信息的说法",
                ],
                answer=quote,
                explanation="正确选项直接来自本地资料片段，其他选项不符合 local-first 与可溯源要求。",
                difficulty=Difficulty.MEDIUM,
                source_citations=[citation] if citation else [],
            )
        )
    for offset in range(min(short_answer_count, len(source_chunks))):
        chunk = source_chunks[(offset + single_choice_count) % len(source_chunks)]
        quote = snippet(chunk.text, 220)
        citation = citation_by_chunk.get(chunk.id)
        questions.append(
            QuizQuestion(
                id=uuid4(),
                type="short_answer",
                question=f"用自己的话解释资料中的知识点 {offset + 1}。",
                answer=quote,
                explanation="答案必须覆盖引用片段中的核心事实，并保留来源可追溯性。",
                difficulty=Difficulty.MEDIUM,
                source_citations=[citation] if citation else [],
            )
        )
    if not questions and source_chunks:
        chunk = source_chunks[0]
        citation = citation_by_chunk.get(chunk.id)
        questions.append(
            QuizQuestion(
                id=uuid4(),
                type="short_answer",
                question="概括这份资料的一个核心信息。",
                answer=snippet(chunk.text, 220),
                explanation="本题用于本地资料不足时的最小可测输出。",
                difficulty=Difficulty.EASY,
                source_citations=[citation] if citation else [],
            )
        )
    return QuizSet(
        id=uuid4(),
        mode=mode,
        sources=SourceSummary(local_chunks=len(citations), web_pages=0),
        questions=questions,
    )
