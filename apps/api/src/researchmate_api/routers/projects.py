"""Expose owner-scoped project creation, lookup, listing, and deletion routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from researchmate_api.dependencies import get_current_user, get_store, raise_api_error
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.project import ProjectCreate, ProjectRecord
from researchmate_api.services.store import ResearchMateRepository

router = APIRouter()


@router.post("/chat/bootstrap", response_model=ProjectRecord)
def bootstrap_personal_chat(
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> ProjectRecord:
    """Return the caller's hidden project used only to reuse chat infrastructure."""
    return repository.ensure_personal_project(user)


# Create a project record.
@router.post("/projects", response_model=ProjectRecord, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> ProjectRecord:
    """Create a project owned by the authenticated caller."""
    return repository.create_project(user, payload)


# List projects owned by the current user.
@router.get("/projects", response_model=list[ProjectRecord])
def list_projects(
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> list[ProjectRecord]:
    """List projects owned by the authenticated caller."""
    return repository.list_projects(user)


# Read a single project; must validate owner user_id.
@router.get("/projects/{project_id}", response_model=ProjectRecord)
def get_project(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> ProjectRecord:
    """Return one project without revealing other owners' resources."""
    project = repository.get_project(user, project_id)
    if project is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return project


# Delete a project and create a local deletion job.
@router.delete("/projects/{project_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_project(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> dict[str, str]:
    """Enqueue cleanup for a caller-owned project."""
    job = repository.delete_project(user, project_id)
    if job is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return {"job_id": str(job.id), "status": job.status}
