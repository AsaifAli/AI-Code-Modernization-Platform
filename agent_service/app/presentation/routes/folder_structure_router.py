"""
Migration plan / folder structure goals API — same contract as migration_service
`/workflow/folder_structure/*` but reads/writes under agent_service Temp layout.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException

from app.domain.services.folder_structure_goals_service import FolderStructureGoalsService
from app.infrastructure.utils.Constants.agent_event import AgentEventMessages
from app.infrastructure.utils.Constants.app_constants import ServiceConstants
from app.infrastructure.utils.auth_client import get_current_user_http as get_current_user_http

router = APIRouter()


@router.get("/folder_structure/{migration_name}")
async def get_folder_structure(migration_name: str, user=Depends(get_current_user_http)):
    try:
        service = FolderStructureGoalsService()
        result = service.get_folder_structure(str(user.id), migration_name)
        return {
            AgentEventMessages.Message: AgentEventMessages.FOLDER_STRUCTURE_FETCHED,
            AgentEventMessages.DATA: result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=ServiceConstants.CODE500, detail=str(e))


@router.put("/folder_structure/update")
async def update_goal_description(
    migration_name: str = Form(...),
    goal_id: int = Form(...),
    parent_goal_id: Optional[int] = Form(None),
    new_description: Optional[str] = Form(None),
    user=Depends(get_current_user_http),
):
    try:
        service = FolderStructureGoalsService()
        result = service.update_goal(
            str(user.id),
            migration_name,
            str(goal_id),
            str(parent_goal_id) if parent_goal_id is not None else None,
            new_description,
        )
        return {
            AgentEventMessages.Message: AgentEventMessages.GOAL_UPDATED_SUCCESS,
            AgentEventMessages.DATA: result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=ServiceConstants.CODE500, detail=str(e))


@router.delete("/folder_structure/delete")
async def delete_goal_description(
    migration_name: str = Form(...),
    goal_id: int = Form(...),
    parent_goal_id: Optional[int] = Form(None),
    user=Depends(get_current_user_http),
):
    try:
        service = FolderStructureGoalsService()
        result = service.delete_goal(
            str(user.id),
            migration_name,
            str(goal_id),
            str(parent_goal_id) if parent_goal_id is not None else None,
        )
        return {
            AgentEventMessages.Message: AgentEventMessages.GOAL_DELETED_SUCCESS,
            AgentEventMessages.DATA: result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=ServiceConstants.CODE500, detail=str(e))


@router.post("/folder_structure/add-item")
async def add_item(
    migration_name: str = Form(...),
    parent_goal_id: int = Form(...),
    name: str = Form(...),
    kind: str = Form(...),
    goal_description: str = Form(...),
    original_file_path: Optional[str] = Form(None),
    user=Depends(get_current_user_http),
):
    try:
        service = FolderStructureGoalsService()
        result = service.add_item(
            user_id=str(user.id),
            migration_name=migration_name,
            parent_goal_id=parent_goal_id,
            name=name,
            kind=kind,
            goal_description=goal_description,
            original_file_path=original_file_path,
        )
        return {"message": "Item added successfully", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
