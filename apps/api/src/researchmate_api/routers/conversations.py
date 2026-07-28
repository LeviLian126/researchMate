from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from researchmate_api.dependencies import (
    get_current_user,
    get_hybrid_store,
    get_store,
    raise_api_error,
    require_admin,
)
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.conversation import (
    ConversationListResponse,
    ConversationMessagesResponse,
    ConversationSummary,
    ConversationUpdate,
    RuntimeRerankConfig,
    RuntimeRerankConfigUpdate,
)
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.store import ResearchMateRepository

router = APIRouter()


@router.get(
    "/projects/{project_id}/conversations",
    response_model=ConversationListResponse,
)
def list_conversations(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> ConversationListResponse:
    items = repository.list_conversations(user, project_id)
    if items is None:
        raise_api_error(404, "PROJECT_NOT_FOUND", "Project was not found.")
    return ConversationListResponse(items=items)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
)
def list_messages(
    conversation_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> ConversationMessagesResponse:
    messages = repository.conversation_messages(user, conversation_id)
    if messages is None:
        raise_api_error(404, "CONVERSATION_NOT_FOUND", "Conversation was not found.")
    return ConversationMessagesResponse(
        conversation_id=conversation_id,
        messages=messages[-200:],
    )


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationSummary,
)
def rename_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> ConversationSummary:
    conversation = repository.rename_conversation(user, conversation_id, payload.title)
    if conversation is None:
        raise_api_error(404, "CONVERSATION_NOT_FOUND", "Conversation was not found.")
    return conversation


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> Response:
    if not repository.delete_conversation(user, conversation_id):
        raise_api_error(404, "CONVERSATION_NOT_FOUND", "Conversation was not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/runtime-config/rerank", response_model=RuntimeRerankConfig)
def read_rerank_config(
    _user: CurrentUser = Depends(require_admin),
    repository: ResearchMateRepository = Depends(get_store),
) -> RuntimeRerankConfig:
    return repository.get_runtime_rerank_config()


@router.put("/admin/runtime-config/rerank", response_model=RuntimeRerankConfig)
def update_rerank_config(
    payload: RuntimeRerankConfigUpdate,
    user: CurrentUser = Depends(require_admin),
    repository: ResearchMateRepository = Depends(get_store),
    qdrant: QdrantHybridStore | None = Depends(get_hybrid_store),
) -> RuntimeRerankConfig:
    if payload.provider == "qdrant" and (qdrant is None or not qdrant.rerank_ready()):
        raise_api_error(
            409,
            "QDRANT_RERANK_NOT_READY",
            "A verified free Qdrant late-interaction index is required before activation.",
        )
    updated = repository.update_runtime_rerank_config(
        user, payload.provider, payload.expected_version
    )
    if updated is None:
        raise_api_error(
            409,
            "RUNTIME_CONFIG_VERSION_CONFLICT",
            "Runtime configuration changed; reload it before retrying.",
        )
    return updated
