from types import SimpleNamespace
from uuid import UUID

from pydantic import SecretStr

from researchmate_api.config import Settings
from researchmate_api.schemas.common import SourceType
from researchmate_api.services.embedding import NvidiaEmbeddingProvider
from researchmate_api.services.qdrant_store import QdrantHybridStore, sparse_text_vector


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            data=[SimpleNamespace(index=index, embedding=[float(index)] * 4096) for index, _ in enumerate(kwargs["input"])]
        )


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddings()


class FakeQdrantClient:
    def __init__(self) -> None:
        self.query_call = None
        self.upsert_call = None
        self.delete_call = None

    def query_points(self, **kwargs):
        self.query_call = kwargs
        return SimpleNamespace(points=[SimpleNamespace(id=UUID(int=1), score=0.9, payload={"chunk_id": "1"})])

    def upsert(self, **kwargs):
        self.upsert_call = kwargs

    def delete(self, **kwargs):
        self.delete_call = kwargs


def settings() -> Settings:
    return Settings(
        app_env="test",
        llm_provider="fake",
        embedding_provider="nvidia",
        nvidia_api_key=SecretStr("fake"),
        qdrant_url="https://qdrant.example.test",
        qdrant_api_key=SecretStr("fake"),
    )


def test_embedding_distinguishes_query_and_passage_modes() -> None:
    client = FakeOpenAIClient()
    provider = NvidiaEmbeddingProvider(settings(), client=client)

    provider.embed(["question"], input_type="query")
    provider.embed(["document"], input_type="passage")

    assert [call["extra_body"]["input_type"] for call in client.embeddings.calls] == [
        "query",
        "passage",
    ]


def test_hybrid_query_has_dense_sparse_rrf_and_all_owner_filters() -> None:
    qdrant = FakeQdrantClient()
    store = QdrantHybridStore(
        settings(), NvidiaEmbeddingProvider(settings(), client=FakeOpenAIClient()), client=qdrant
    )

    results = store.query(
        user_id="user-1",
        project_id="project-1",
        source_type=SourceType.LOCAL_DOC,
        text="retrieval augmented generation",
        limit=5,
    )

    call = qdrant.query_call
    assert results[0]["score"] == 0.9
    assert [prefetch.using for prefetch in call["prefetch"]] == ["sparse", "dense"]
    assert call["query_filter"] is not None
    assert {condition.key for condition in call["query_filter"].must} == {
        "user_id",
        "project_id",
        "source_type",
    }


def test_sparse_vector_is_stable_and_sorted() -> None:
    first = sparse_text_vector("RAG retrieval retrieval")
    second = sparse_text_vector("RAG retrieval retrieval")

    assert first == second
    assert first.indices == sorted(first.indices)


def test_upsert_uses_named_vectors_and_owner_payload() -> None:
    from researchmate_api.services.store import ChunkEntry

    qdrant = FakeQdrantClient()
    store = QdrantHybridStore(
        settings(), NvidiaEmbeddingProvider(settings(), client=FakeOpenAIClient()), client=qdrant
    )
    chunk = ChunkEntry(
        id=UUID("20000000-0000-4000-8000-000000000001"),
        user_id=UUID("20000000-0000-4000-8000-000000000002"),
        project_id=UUID("20000000-0000-4000-8000-000000000003"),
        document_id=UUID("20000000-0000-4000-8000-000000000004"),
        source_type=SourceType.LOCAL_DOC,
        source_title="Evidence",
        text="hybrid evidence",
        page_no=7,
    )

    store.upsert_chunks([chunk], pipeline_version="pipeline-v1")

    assert qdrant.upsert_call["collection_name"] == "researchmate_chunks"
    point = qdrant.upsert_call["points"][0]
    assert set(point.vector) == {"dense", "sparse"}
    assert point.payload["user_id"] == str(chunk.user_id)
    assert point.payload["project_id"] == str(chunk.project_id)
    assert point.payload["chunk_id"] == str(chunk.id)
    assert point.payload["pipeline_version"] == "pipeline-v1"


def test_delete_points_keeps_owner_filter_at_the_vector_boundary() -> None:
    qdrant = FakeQdrantClient()
    store = QdrantHybridStore(
        settings(), NvidiaEmbeddingProvider(settings(), client=FakeOpenAIClient()), client=qdrant
    )

    store.delete_points(["point-1"], user_id="user-1", project_id="project-1")

    selector = qdrant.delete_call["points_selector"]
    keys = {condition.key for condition in selector.filter.must if hasattr(condition, "key")}
    assert keys == {"user_id", "project_id"}
    assert qdrant.delete_call["wait"] is True
