from fastapi import APIRouter, Depends

from researchmate_api.dependencies import (
    get_chat_provider,
    get_current_user,
    get_hybrid_store,
    get_web_search,
    get_store,
    raise_api_error,
)
from researchmate_api.schemas.ask import AskRequest, AskResponse
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.services.grounded_query import GroundedQueryError, GroundedQueryService
from researchmate_api.services.llm import ChatProvider
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.web_search import TavilyWebSearchProvider
from researchmate_api.services.store import ResearchMateRepository


router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
    chat_provider: ChatProvider | None = Depends(get_chat_provider),
    hybrid_store: QdrantHybridStore | None = Depends(get_hybrid_store),
    web_search: TavilyWebSearchProvider | None = Depends(get_web_search),
) -> AskResponse:
    try:
        return GroundedQueryService(
            repository=repository,
            chat_provider=chat_provider,
            hybrid_store=hybrid_store,
            web_search=web_search,
        ).execute(user, payload)
    except GroundedQueryError as exc:
        raise_api_error(exc.status_code, exc.code, exc.message)
