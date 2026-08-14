"""Own in-memory wiki page storage and retrieval."""

from __future__ import annotations

from threading import RLock
from typing import TYPE_CHECKING
from uuid import UUID

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.services._store_models import WikiPage


class WikiStoreMixin:
    """Own in-memory wiki page CRUD for lightweight compiled documents."""

    if TYPE_CHECKING:
        _lock: RLock
        wiki_pages: dict[UUID, WikiPage]

        def get_project(self, user: CurrentUser, project_id: UUID) -> object | None: ...

    def store_wiki_pages(self, pages: list[WikiPage]) -> None:
        """Persist wiki pages keyed by their stable ID."""
        with self._lock:
            for page in pages:
                self.wiki_pages[page.id] = page

    def project_wiki_pages(self, user: CurrentUser, project_id: UUID) -> list[WikiPage]:
        """Return all wiki pages visible to the caller within one project."""
        with self._lock:
            return [
                page
                for page in self.wiki_pages.values()
                if page.user_id == user.id and page.project_id == project_id
            ]

    def document_wiki_pages(self, user: CurrentUser, document_id: UUID) -> list[WikiPage]:
        """Return wiki pages compiled from one owned document."""
        with self._lock:
            return [
                page
                for page in self.wiki_pages.values()
                if page.user_id == user.id and page.document_id == document_id
            ]

    def delete_document_wiki_pages(self, document_id: UUID) -> None:
        """Remove all wiki pages derived from one document."""
        with self._lock:
            for page_id in [
                pid for pid, page in self.wiki_pages.items() if page.document_id == document_id
            ]:
                del self.wiki_pages[page_id]
