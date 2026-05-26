from uuid import UUID

from fastapi import APIRouter, Depends, status

from researchmate_api.dependencies import get_current_user, raise_api_error
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.project import ProjectCreate, ProjectRecord
from researchmate_api.services.store import store


router = APIRouter()


# 创建项目记录。
@router.post("/projects", response_model=ProjectRecord, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, user: CurrentUser = Depends(get_current_user)) -> ProjectRecord:
    return store.create_project(user, payload)


# 列出当前用户项目。
@router.get("/projects", response_model=list[ProjectRecord])
def list_projects(user: CurrentUser = Depends(get_current_user)) -> list[ProjectRecord]:
    return store.list_projects(user)


# 读取单个项目，必须校验 owner user_id。
@router.get("/projects/{project_id}", response_model=ProjectRecord)
def get_project(project_id: UUID, user: CurrentUser = Depends(get_current_user)) -> ProjectRecord:
    project = store.get_project(user, project_id)
    if project is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return project


# 删除项目并创建本地 deletion job。
@router.delete("/projects/{project_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_project(project_id: UUID, user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    job = store.delete_project(user, project_id)
    if job is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return {"job_id": str(job.id), "status": job.status}
