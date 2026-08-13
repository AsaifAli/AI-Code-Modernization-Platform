from typing import Optional

from pydantic import BaseModel
from app.infrastructure.utils.Constants.app_constants import AgentConstants


class RunTeamRequest(BaseModel):
    source_path: str
    migration_name: str
    description: str
    target_language: Optional[str] = None
    target_path: Optional[str] = None
    user_id: Optional[str] = None
    github_token: Optional[str] = None


class TaskAcceptedResponse(BaseModel):
    task_id: str
    status: str = AgentConstants.TASK_STATUS_ACCEPTED
    message: str
    detected_target_language: Optional[str] = None
    detected_target_framework: Optional[str] = None
    detected_target_architecture: Optional[str] = None
    detected_is_frontend: bool = False
    detected_target_frontend: Optional[str] = None
    detected_target_frontend_architecture: Optional[str] = None
    detected_execution_mode: Optional[str] = None
    detected_unit_test_framework: Optional[str] = None


class TaskStatusResponse(BaseModel):
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[str] = None


class ArchitectureRequest(BaseModel):
    architecture_option: str
    target_path: str


class ArchitectureResponse(BaseModel):
    selected_architecture: str
    message: str


class ChatAskRequest(BaseModel):
    migration_name: str
    question: str
    source_file_path: Optional[str] = None
    is_target: bool = False


class ChatAskResponse(BaseModel):
    answer: str


class MigrationReportRequest(BaseModel):
    migration_name: str
    persist: bool = True
    include_markdown: bool = False
    require_migrated: bool = True


class MigrationShowcaseRequest(BaseModel):
    migration_name: str
    persist: bool = True


class PostMigrationRunRequest(BaseModel):
    migration_name: str
    migrated_code_path: Optional[str] = None
    persist: bool = True


class PostMigrationQualityRequest(BaseModel):
    migration_name: str
    migrated_code_path: Optional[str] = None
