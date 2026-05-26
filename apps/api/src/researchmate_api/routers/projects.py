from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from researchmate_api.dependencies import get_current_user, not_implemented_detail
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.project import ProjectCreate, ProjectRecord


router = APIRouter()


# 创建项目记录，具体数据库写入由后续 agent 实现。
@router.post("/projects", response_model=ProjectRecord, status_code=status.HTTP_201_CREATED)
def create_project(_: ProjectCreate, user: CurrentUser = Depends(get_current_user)) -> ProjectRecord:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("PROJECT_CREATE_NOT_IMPLEMENTED"),
    )


# 列出当前用户项目，具体查询由后续 agent 实现。
@router.get("/projects", response_model=list[ProjectRecord])
def list_projects(user: CurrentUser = Depends(get_current_user)) -> list[ProjectRecord]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("PROJECT_LIST_NOT_IMPLEMENTED"),
    )


# 读取单个项目，后续必须校验 owner user_id。
@router.get("/projects/{project_id}", response_model=ProjectRecord)
def get_project(project_id: UUID, user: CurrentUser = Depends(get_current_user)) -> ProjectRecord:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("PROJECT_GET_NOT_IMPLEMENTED"),
    )


# 删除项目，后续必须创建 deletion job 并清理 DB/R2/Qdrant/Redis。
@router.delete("/projects/{project_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_project(project_id: UUID, user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("PROJECT_DELETE_NOT_IMPLEMENTED"),
    )

