import os
import logging
from pathlib import Path
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Constants:
    
    migration_name = ""
    source_name = ""
    source_path = ""
    migration_path = ""
    target_language = ""
    target_path = ""
        
        

class ServiceConstants:
    
    VERSION="1.0"
    
    MIGRATION_SERVICE_PREFIX="/workflow"
    
    MIGRATION_SERVICE_TAGS="Workflow Service"
    
    CODE404 = 404
    CODE500 = 500
    CODE400 = 400
    CODE403=403
    CODE429= 429
    CODE200= 200
    CODE401=401
    IN_PROGRESS= "In_Progress"
    ERROR = "Error"
    COMPLETE = "Complete"
    SUCCESS= "Success"
    STATUS= "status"
    RESOURCE_EXHAUSTED= "RESOURCE_EXHAUSTED"
    WORKFLOW="workflow"
    FILE="workflow/file"
    STATUS="workflow/status"
    CLEANUP="workflow/cleanup"
    DOWNLOAD="workflow/download"
    MIGRATION_LIST="workflow/migration_list"
    MIGRATION_EVENT_HISTORY="workflow/migration_event_history"
    MIGRATION_PLAN="workflow/folder_structure"
    GATEWAY_SERVICE="gateway_service"
    MIGRATION_WORKFLOW_SERVICE= "Migration Workflow Service"
    USER_MESSAGE="Manages user authentication, authorization, and OAuth integration."
    AGENT_RUNNING_MESSAGE = "Agent Orchestrator Service is running"
    
    "🔐 User Authentication Service running on port 8007"
    
    MIGRATION_FILE_SERVICE = "Migration File Service"
    FILE_SERVICE_PREFIX = "/file"
    FILE_SERVICE_TAGS = ["File Service"]
    
    MIGRATION_STATUS_SERVICE = "Migration Status Service"
    STATUS_SERVICE_PREFIX = "/status"
    STATUS_SERVICE_TAGS = ["Status Service"]
    
    MIGRATION_EVENT_HISTORY_SERVICE = "Migration Event History Service"
    MIGRATION_EVENT_HISTORY_SERVICE_PREFIX = "/migration_event_history"
    MIGRATION_EVENT_HISTORY_SERVICE_TAGS = ["History Service"]
    
    MIGRATION_LIST_SERVICE = "Migration List Service"
    MIGRATION_LIST_SERVICE_PREFIX = "/migration_list"
    MIGRATION_LIST_SERVICE_TAGS = ["Migration List"]
    
    MIGRATION_DOWNLOAD_SERVICE = "Migration Download Service"
    MIGRATION_DOWNLOAD_SERVICE_PREFIX = "/download"
    MIGRATION_DOWNLOAD_SERVICE_TAGS = ["Download Service"]
    
    MIGRATION_CLEANUP_SERVICE = "Migration Cleanup Service"
    MIGRATION_CLEANUP_SERVICE_PREFIX = "/cleanup"
    MIGRATION_CLEANUP_SERVICE_TAGS = ["Cleanup Service"]
    
    MENU_BUILDER_SERVICE = "Menu Builder Service"
    MENU_BUILDER_SERVICE_PREFIX = "/menu"
    MENU_BUILDER_SERVICE_TAGS = ["Menu Builder"]
    MENU_BUILDER_SERVICE_ENDPOINT = "application.app.domain.services.menu_builder_service.main:app"
    
    TEMP_FOLDER = "Temp"
    SOURCE_FOLDER = "Source"
    TARGET_FOLDER = "Dest"
    UPLOAD_PREFIX = "upload_"
    ZIP_SUFFIX = ".zip"
    GIT_HOSTS = ["github.com", "gitlab.com", ".git"]
    GIT_PERMISSION_ERRORS = [
        "exit status 128",
        "permission denied",
        "authentication failed"
    ]
    
    GATEWAY_MESSAGE="🧩 API Gateway is running on port 8000"
    
    AGENT_ENDPOINT="main:app"
    FOLDER_STRUCTURE_WITH_GOALS_FILE = "folder_structure_with_goals.json"
    MIGRATION_PLAN_FILE = "migration_plan.json"


class AgentConstants:
    # Names emitted by the lightweight migration-event compatibility helpers.
    # Keep these alongside the other shared agent constants so helper modules
    # can be imported safely during application startup and image builds.
    SCANNER_AGENT = "scanner"
    SCAN_MIGRATION_START = "scan_migration_start"
    PLANNING_AGENT = "planning"
    PLANNING_AGENT_STARTED = "planning_started"

    TASK_STATUS = "status"
    TASK_RESULT = "result"
    TASK_ERROR = "error"
    TASK_STARTED_AT = "started_at"
    TASK_COMPLETED_AT = "completed_at"

    TASK_STATUS_ACCEPTED = "accepted"
    TASK_STATUS_RUNNING = "running"
    TASK_STATUS_COMPLETED = "completed"
    TASK_STATUS_FAILED = "failed"
    TASK_STATUS_SUCCESS = "success"
    TASK_STATUS_ERROR = "error"

    RESPONSE_MESSAGE = "message"
    RESPONSE_OUTPUT = "output"

    TARGET_LANGUAGE = "target_language"
    TARGET_FRAMEWORK = "target_framework"
    TARGET_ARCHITECTURE = "target_architecture"
    TARGET_FRONTEND = "target_frontend"
    TARGET_FRONTEND_ARCHITECTURE = "target_frontend_architecture"
    IS_FRONTEND = "is_frontend"

    DEFAULT_TARGET_LANGUAGE = "python"
    DEFAULT_TARGET_FRAMEWORK = "fastapi"
    DEFAULT_TARGET_ARCHITECTURE = "layered"
    DEFAULT_TARGET_FRONTEND = "react"
    DEFAULT_FRONTEND_ARCHITECTURE = "layered"
    DEFAULT_STANDARD_FRAMEWORK = "standard"
    DEFAULT_VUE_FRONTEND = "vue"
    FRONTEND_HINT = "frontend"

    ARCHITECTURE_MAP = {
        "1": "Laravel + Clean MVC",
        "2": "Symfony + Hexagonal",
        "3": "Microservices using Lumen",
    }

    TASK_NOT_FOUND = "Task not found"
    AGENT_TEAM_EXECUTION_QUEUED = "Agent team execution queued"
    WORKFLOW_EXECUTION_QUEUED = "workflow execution queued"
    HEALTHY = "healthy"
    INTERNAL_SERVER_ERROR = "Internal server error"
    TEMP_MIGRATION_DELETED = "Temp migration '{migration_name}' deleted in agent_service"
    MIGRATION_NOT_FOUND_FOR_USER = "Migration '{migration_name}' not found for user '{user_id}'"
    PROCESSED_MIGRATION_NOT_FOUND_FOR_USER = "Processed migration '{migration_name}' not found for user '{user_id}'"
    ARCHITECTURE_SELECTED_FOR_TARGET_PATH = "Architecture '{selected_architecture}' selected for target path '{target_path}'"
    TEAM_FINISHED_LOG = "Team finished: %s"
    UNEXPECTED_RESULT_FORMAT = "Unexpected result format from team"
    GITHUB_TOKEN_HEADER = "X-Github-Token"
class MigrationScope:
    SCOPE_SOURCE = 1
    SCOPE_TARGET = 2
    SCOPE_SOURCE_NAME = "source"
    SCOPE_TARGET_NAME = "target"


class PathConstants:
    TEMP_DIR = os.path.abspath("Temp")
    Project_path= os.getcwd()
    
class ArtifactType:
    SCANNER_OUTPUT = "scanner_output"
    AST = "ast"
    TECH = "tech"
    DEPENDENCY_GRAPH = "dependency_graph"
    SEMANTIC_IR = "semantic_ir"
    SYNTACTIC_AST = "syntactic_ast"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    MIGRATION_PLAN = "migration_plan"
    FOLDER_STRUCTURE_GOALS = "folder_structure_goals"
