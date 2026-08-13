# app/infrastructure/utils/agent_event_strings.py
class AgentEventMessages:
    EMPTY_STRING = ""
    RESTART_PAYLOAD = "restart_payload"
    MIGRATION_STATUS = "migration_status"
    AI_QUOTA_ERROR = "AI quota exhausted"
    NO_CONFIG_FOUND = "No previous migration config found for {migration_name}"
    EVENT = "event"
    USER_ID = "user_id"
    DETAILS = "details"
    TYPE_ = "type_"
    CUSTOM = "custom"
    DATA = "data"
    VIEW_TYPE = "view_type"
    IS_LAST_MESSAGE = "is_last_message"
    EXTRA = "extra"
    IS_HIDDEN = "is_hidden"
    TOKEN = "token"
    MIGRATION_NAME = "migration_name"
    SOURCE_PATH = "source_path"
    TARGET = "target"
    TARGET_PATH = "target_path"
    GITHUB_METADATA = "github_metadata"
    GITHUB_TOKEN = "github_token"
    AUTHORIZATION = "authorization"
    BEARER_WORD = "Bearer"
    BEARER = "Bearer {token}"
    ACTION = "action"
    RESTART = "restart"
    RESTART_COMPLETE = "restart_complete"
    Message = "message"   
    RESTART_MIGRATION = "Restarting migration `{migration_name}`..."
    RESULT = "result"
    GET_MIGRATION_DATA = "getMigrationData"
    GET_MENU_DATA = "getMenuData"
    GET_MIGRATION_ERROR = "First message must be 'getMigrationData'"
    GET_MENU_ERROR = "First message must be 'getMenuData'"
    INVALID_OR_EXPIRED_TOKEN = "Invalid or expired token"
    USER_ID_MISMATCH = "User Id Mismatch"
    WORKFLOW_API_FAILED = "Workflow API failed: {response}"
    MIGRATION_RESTART_SUCCESS = "Migration was successfully restarted."
    CONFIG_JSON_MISSING = "Config.json is missing required parameters"
    MIGRATION_FAILED_GENERIC = "An unexpected error occurred during migration."
    MIGRATION_FAILED_QUOTA = "AI provider quota exceeded. Please try again later."
    GENERATE_RESPONSE_JSON = "Generating source_response.json using LLM analysis for maximum accuracy"
    SCANNER_OUTPUT_NOT_FOUND = "Error: source_scanner_output.json not found. Run scanner first."
    CALLING_UTILITY_AGENT = "🤖 Calling utility agent for intelligent response analysis..."
    GENERATE_SEMANTIC_IR = "Generate Semantic IR from syntactic AST using LLM enrichment."
    RUNNING_ADVANCED_SCANNER = "Running Advanced Scanner: generates syntactic AST and semantic IR."
    SERVICE_NOT_FOUND = "Service '{service_name}' not found in DB"
    EVALUATING_PROJECT = "Analysing the project.."
    MIGRATION_DIR_NOT_FOUND = "Migration directory does NOT exist!"
    MIGRATION_DIR_EXISTS = "Migration directory exists\nFiles: {file_count}"
    PLANNING_AGENT_STARTED_MSG = "Planning Agent Started"
    PLANNING_AGENT_SCANNER_OUTPUT_NOT_FOUND_MSG = "❌ Error: source_scanner_output.json not found in migration_dir"
    PLANNING_FOLDER_SAVED_MSG = "✓ Folder structure saved"
    PLANNING_TARGET_FOLDER_SAVED_MSG = "{target_language} folder structure saved."
    PLANNING_GOALS_CREATED_MSG = "Generate and save goals.json to migration directory."
    PLANNING_GOALS_SAVED_MSG = "✓ Goals saved"
    KNOWLEDGE_BASE_CREATION_STARTED_MSG = "Knowledge Base has Started"
    KNOWLEDGE_BASE_CREATION_COMPLETED_MSG = "Knowledge Base created with SEMANTIC IR! Total chunks embedded: {chunk_count}"
    KNOWLEDGE_BASE_QUERY_MSG = "Query the Knowledge Base using semantic search. Returns relevant information from ALL stored artifacts."
    KNOWLEDGE_BASE_RESPONSE_MSG = "KB returned semantic IR-based response"
    CONVERSION_AGENT_APPLYING_RULES_MSG = "Applying generic conversion rules to code."
    CONVERSION_AGENT_STARTED_MSG = "Conversion Agent Started"
    CONVERSION_AGENT_FILLING_STRATEGY_MSG = "Loading project structure and migration goals."
    CONVERSION_AGENT_PROGRESS_MSG = "Conversion Agent progress update"
    CONVERSION_AGENT_POST_MIGRATION_ANALYSIS_MSG = "Run complete post-migration analysis by calling the SAME FUNCTIONS used by pre-migration agents. This ensures consistency between original and migrated code analysis."
    CONVERSION_AGENT_POST_MIGRATION_ANALYSIS_STARTED_MSG = "Starting post-migration analysis. Using same functions as pre-migration agents for consistency..."
    CONVERSION_USING_COMPLEXITY = "Using complexity analysis for intelligent file preservation"
    CONVERSION_FILE_PRESERVED_MSG = "File preserved based on complexity analysis"
    CONVERSION_FILE_REGENERATED_MSG = "File regenerated due to complexity mismatch"
    CONVERSION_AGENT_FILE_STATS_MSG = "Pre-migration analysis files generated"
    PHASE_5_EXTRACTING_FOLDER_STRUCTURE = "PHASE 5: Extracting folder structure..."
    NAME_SERVICE = "__main__"
    MIGRATION_SERVICE_DESCRIPTION = "Executes migration workflows via orchestrator and rules."
    MIGRATION_SERVICE_MESSAGE = "⚙️ Migration Workflow Service running on port 8003"
    FILE_PREPARED_SUCCESSFULLY = "File prepared successfully"
    FILE_PREPARATION_FAIL = " File preparation failed: {e}"
    FILE_SERVICE_DESCRIPTION = "Handles zip file uploads, extraction, and source path setup."
    FILE_SERVICE_MESSAGE = "📁 Migration File Service is running."
    STATUS_SERVICE_DESCRIPTION = "Provides status for migrations (in-progress/completed/unknown)."
    STATUS_SERVICE_MESSAGE = "📈 Migration Status Service is running."
    MIGRATION_EVENT_HISTORY_DESCRIPTION = "Provides history for migrations."
    MIGRATION_EVENT_HISTORY_MESSAGE = "📈 Migration Event History Service is running."
    MIGRATION_LIST_SERVICE_DESCRIPTION = "Lists all migrations belonging to the authenticated user."
    MIGRATION_LIST_SERVICE_MESSAGE = "Migration List Service is running 🚀"
    MIGRATION_DOWNLOAD_SERVICE_DESCRIPTION = "Serves provides download link."
    MIGRATION_DOWNLOAD_SERVICE_MESSAGE = "📦 Migration Download Service running"
    MIGRATION_CLEANUP_SERVICE_DESCRIPTION = "Handles deletion and cleanup of migration temporary data."
    MIGRATION_CLEANUP_SERVICE_MESSAGE = "🧹 Migration Cleanup Service running"
    MENU_BUILDER_SERVICE_DESCRIPTION = "Provides menu for migrations."
    MENU_BUILDER_SERVICE_MESSAGE = "📈 Menu Builder Service running"
    GITHUB = "github"
    CLONE_URL = "clone_url"
    REPO = "repo"
    PROVIDER = "provider"
    GITHUB_METADATA = "github_metadata"
    REPO_CLONE_FAILED = "Repository clone failed"
    INVALID_SOURCE_PATH = "Provided source_path does not exist"
    SOURCE_REQUIRED = "Either zip_file or source_path must be provided"
    GITHUB_PERMISSION_ERROR = "Permission denied: You cannot clone a private repo without Private Access Token"
    EMAIL = "email"
    EMAIL_USERNAME = "email/username"
    PASSWORD = "password"
    CODE = "code"
    ACCESS = "access"
    REFRESH = "refresh"
    TYPE = "type"
    SUB = "sub"
    EXP = "exp"
    TOKEN_TYPE = "token_type"
    ID = "id"
    ACCESS_TOKEN = "access_token"
    REFRESH_TOKEN = "refresh_token"
    MIGRATION_GATEWAY_Message = "Unified Migration API Gateway"
    MIGRATION_GATEWAY_DESCRIPTION = "Routes all migration microservice traffic through a single entry point."
    SCANNER_AGENT_OUTPUT="Here is the output for scanner agent"
    SCANNER_AGENT_FRAMEWORK="Here is the framework for Project"
    SCANNER_AGENT_LANGUAGES="Here is the language for Project"
    GIT_TOKEN="Git Token"
    FOLDER_STRUCTURE_FILE_NOT_FOUND = "Folder structure file not found."
    GOAL_NOT_FOUND = "Goal ID + Parent Goal ID not found."
    FOLDER_STRUCTURE_FETCHED = "Folder structure fetched successfully."
    GOAL_UPDATED_SUCCESS = "Goal updated successfully."
    GOAL_DELETED_SUCCESS = "Goal deleted successfully."
    MIGRATION_PLAN_ALREADY_PRESENT="Migration_Plan_is_already_present"
    MIGRATION_PLAN_SAVED_AND_UPDATED="Migration_Plan_is_saved_and_updated"
    # New Agent Event Migration Starterd Messages
    CODE_CLONING = "Your code has been cloned and I’m examining its structure, dependencies, and behavior."
    MODULE_ANALYSIS = "I’ll go through each module one by one — code, assets, and configurations included."
    LOG_STEPS = "For every step, I’ll surface detailed logs so you can follow the progress clearly."
    WORKING_STEPS = "This way, you’ll always know what I’m working on and why."
    BEGIN_STEPS = "Let's begin 🚀"
    # Dynamic intro message with migration name
    STARTING_ANALYSIS_WITH_NAME = "Hi! I'm starting the analysis of your project {migration_name} that you have shared."
    # ------------- Add Constant here ---------------- 
    LEGACY_CODE_ANALYSIS = "Next, let's analyze the Legacy Code Analysis. I'll show the logs step by step."
    
    # New Agent Event Migration Completed Messages
    MIGRATION_WORKFLOW_COMPLETED = "Migration workflow completed successfully."
    ALL_STEPS_COMPLETED = "All migration steps have been completed successfully. The migrated codebase is ready for review and deployment."
    MIGRATION_COMPLETED = "Migration completed successfully."
    STEPS_PROCESSED = "All steps have been processed successfully."
    ANALYSIS_COMPLETED = "Migration analysis completed."
    REVIEW_LOGS = "You can now review the detailed logs of each module above."
    GITHUB_PUSH_SUCCESS = "The migrated codebase has been successfully pushed to the {branch_name} Git branch for review."

    
    # Migration event message constants
    STEP_START_MESSAGE = "Now I am picking the step: {step_name}"
    STEP_DESCRIPTION_MESSAGE = "This step analyzes and processes {step_name} as part of the migration workflow."
    SUBSTEP_GENERATED_SUCCESS = "{substep_type_name} generated successfully."
    STEP_FILE_GENERATED_SUCCESS = "{step_name} file generated successfully."
    
    # Scanner Agent Messages (Step 1 - Legacy Code Analysis)
    SCANNER_AGENT_INITIALIZED = "Scanner agent initialized."
    ANALYZING_SOURCE_FILES = "Analyzing source files..."
    PROJECT_ANALYSIS_DESCRIPTION = "I've cloned the code and started examining its structure, dependencies, and runtime behavior."
    SEMANTIC_IR_GENERATION_STARTED = "Semantic IR generation started."
    CODE_ANALYSIS_COMPLETED = "Code analysis completed successfully."
    LEGACY_CODE_STEP_RESULT = "The legacy codebase was successfully scanned and converted into an intermediate representation, forming a reliable foundation for migration planning."
    NO_SEMANTIC_IR_GENERATED = "No Semantic IR generated!"
    ERROR_LEGACY_CODE_ANALYSIS = "Error in Legacy Code Analysis: {error}"
    
    # Scanner Agent Messages (Step 2 - Identified Entities)
    ENTITY_DETECTION_STARTED = "Entity detection started."
    ENTITIES_DISCOVERED = "Entities discovered: {entity_names}."
    ENTITIES_DISCOVERED_NONE = "Entities discovered: None."
    RELATIONSHIPS_MAPPED_SUCCESS = "Relationships mapped successfully."
    IDENTIFIED_ENTITIES_STEP_RESULT = "Core domain entities and relationships were identified, enabling accurate database modeling and API design in the target system."
    ERROR_IDENTIFIED_ENTITIES = "Error in Identified Entities: {error}"
    
    # --------------------- Added Code Target Response ---------------------------------------#
    # Scanner Agent Messages (Step 11 - Target Code Analysis)
    TARGET_CODE_ANALYSIS_STARTED = "Started analyzing target code structure."
    TARGET_CODE_ANALYSIS_COMPLETED = "Target code analysis completed successfully."
    TARGET_CODE_ANALYSIS_STEP_RESULT = "Target code structure was analyzed to understand the destination architecture and ensure compatibility with the migration plan."
    ERROR_TARGET_CODE_ANALYSIS = "Error in Target Code Analysis: {error}"    
    # --------------------- Added Code Target Response ---------------------------------------#
    
    # Scanner Agent Messages (Step 3 - Assets & Configuration)
    STARTED_REVIEWING_ASSETS = "Started reviewing project assets."
    CONFIG_FILES_LOADED_FOUND = "Configuration files loaded and verified. Found {count} configuration files."
    CONFIG_FILES_LOADED_NONE = "No configuration files detected in the project."
    NO_MISSING_DEPS_FOUND = "No missing dependencies found."
    NO_MISSING_DEPS_WITH_NON_CONVERTIBLE = "No missing dependencies found. {count} non-convertible files identified."
    ASSETS_CONFIG_ANALYSIS_COMPLETED = "Assets and configuration analysis completed."
    ASSETS_CONFIG_STEP_RESULT = "All assets and configuration files were validated, confirming environment readiness and reducing migration risk."
    ASSETS_CONFIG_STEP_RESULT_NO_FILES = "Project assets and configuration were reviewed. No configuration files or non-convertible files detected, indicating a clean migration path."
    ERROR_ASSETS_CONFIGURATION = "Error in Assets & Configuration: {error}"


    # Planning Agent Messages (Step 8 - Migration Plan)
    PLANNING_AGENT_INITIALIZED = "Planning agent initialized."
    COMPLEXITY_ANALYSIS_COMPLETED = "Complexity analysis completed successfully."
    STARTED_GENERATING_MIGRATION_PLAN = "Started generating migration plan structure."
    PROJECT_STRUCTURE_GOALS_GENERATED = "Project structure and goals generated successfully."
    MIGRATION_PLAN_STEP_RESULT = "Migration plan structure was generated, outlining the target project organization and conversion goals."
    ERROR_MIGRATION_PLAN = "Error in Migration Plan: {error}"
    PLANNING_SCANNER_OUTPUT_NOT_FOUND_DETAIL = (
        " Error: source_scanner_output.json not found in {migration_dir}\n\n"
        "REQUIRED STEPS:\n"
        "1. Run AST Agent FIRST:\n"
        "   - Call run_project_scanner(project_path='<your_source_code_path>')\n"
        "2. Then call generate_project_structure_with_goals()\n\n"
        "The scanner must analyze the source code before structure generation."
    )
    PLANNING_COMPLEXITY_SCORE_NOT_FOUND_DETAIL = (
        " Error: complexity_score.json not found in {migration_dir}\n\n"
        "REQUIRED STEPS:\n"
        "1. Run AST Agent FIRST:\n"
        "   - Call run_project_scanner(project_path='<your_source_code_path>')\n"
        "2. Then call generate_project_structure_with_goals()\n\n"
        "The scanner must analyze the source code before structure generation."
    )
    # Note: Validation errors like "No valid data in source_scanner_output.json" are in ValidationMessages
    # These messages below are user-facing workflow event stream messages sent to frontend
    PLANNING_GENERIC_ERROR = "Error: {error}"
    
    # Conversion Agent Messages (Step 9 - Migration Progress)
    CONVERSION_AGENT_INITIALIZED = "Conversion agent initialized."
    FILL_PROJECT_CODE_STRATEGY = "Fill project code file by file to avoid truncation. Fill code with multi-strategy approach: KB → AST → Template."
    PROJECT_STRUCTURE_LOADED = "Project structure loaded successfully."
    STARTING_CODE_GENERATION = "Starting code generation process."
    CODE_GENERATION_COMPLETED = "Code generation completed. {files_created} files created, {folders_created} folders created."
    MIGRATION_PROGRESS_STEP_RESULT = "Migration progress completed successfully. Generated {files_created} files and {folders_created} folders in the target language."
    ERROR_MIGRATION_PROGRESS = "Error in Migration Progress: {error}"
    CONVERSION_GOALS_FILE_NOT_FOUND = "Error: folder_structure_with_goals.json not found at {path}"
    CONVERSION_GENERIC_ERROR = "Error: {error}"
    
    # Step IDs and Step Names (for consistent step identification)
    LEGACY_CODE_STEP_ID = "step-1"
    LEGACY_CODE_STEP_NAME = "Legacy Code Analysis"
    
    IDENTIFIED_ENTITIES_STEP_ID = "step-2"
    IDENTIFIED_ENTITIES_STEP_NAME = "Identified Entities"

    # --------------------- Added Code Target Response ---------------------------------------# 
    TARGET_CODE_ANALYSIS_STEP_ID = "step-11"
    TARGET_CODE_ANALYSIS_STEP_NAME = "Target Code Analysis"
    # --------------------- Added Code Target Response ---------------------------------------#
        
    ASSETS_CONFIG_STEP_ID = "step-3"
    ASSETS_CONFIG_STEP_NAME = "Assets & Configuration"
    
    RISK_ASSESSMENT_STEP_ID = "step-7"
    RISK_ASSESSMENT_STEP_NAME = "Risk Assessment"
    
    MIGRATION_PLAN_STEP_ID = "step-8"
    MIGRATION_PLAN_STEP_NAME = "Migration Plan"
    
    MIGRATION_PROGRESS_STEP_ID = "step-9"
    MIGRATION_PROGRESS_STEP_NAME = "Migration Progress"
    
    COMPLETION_SUMMARY_STEP_ID = "step-10"
    COMPLETION_SUMMARY_STEP_NAME = "Completion Summary"
    
    # Step Duplicate Prevention Flags (for tracking sent events per migration)
    # Step 1 - Legacy Code Analysis
    LEGACY_CODE_STEP_START_SENT_FLAG = "step_1_start_sent"
    LEGACY_CODE_STEP_DESCRIPTION_SENT_FLAG = "step_1_description_sent"
    
    # Step 2 - Identified Entities
    IDENTIFIED_ENTITIES_STEP_START_SENT_FLAG = "step_2_start_sent"
    IDENTIFIED_ENTITIES_STEP_DESCRIPTION_SENT_FLAG = "step_2_description_sent"
    
    # --------------------- Added Code Target Response ---------------------------------------#
    # Step 11 - Target Code Analysis
    TARGET_CODE_ANALYSIS_STEP_START_SENT_FLAG = "step_11_start_sent"
    TARGET_CODE_ANALYSIS_STEP_DESCRIPTION_SENT_FLAG = "step_11_description_sent"
    # --------------------- Added Code Target Response ---------------------------------------#
        
    # Step 3 - Assets & Configuration
    ASSETS_CONFIG_STEP_START_SENT_FLAG = "step_3_start_sent"
    ASSETS_CONFIG_STEP_DESCRIPTION_SENT_FLAG = "step_3_description_sent"
    
    # Step 8 - Migration Plan
    MIGRATION_PLAN_STEP_START_SENT_FLAG = "step_8_start_sent"
    MIGRATION_PLAN_STEP_DESCRIPTION_SENT_FLAG = "step_8_description_sent"
    
    # Step 9 - Migration Progress
    MIGRATION_PROGRESS_STEP_START_SENT_FLAG = "step_9_start_sent"
    MIGRATION_PROGRESS_STEP_DESCRIPTION_SENT_FLAG = "step_9_description_sent"
    
    # Step 10 - Completion Summary
    COMPLETION_SUMMARY_STEP_START_SENT_FLAG = "step_10_start_sent"
    COMPLETION_SUMMARY_STEP_DESCRIPTION_SENT_FLAG = "step_10_description_sent"