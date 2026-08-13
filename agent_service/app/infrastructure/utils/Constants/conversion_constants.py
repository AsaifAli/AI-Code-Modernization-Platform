class ConversionConstants:

    WORKFLOW_NAME = "Conversion Workflow"
    WORKFLOW_DESCRIPTION = "Convert source project to target language using knowledge base context"
    STEP_NAME_GENERATE_CODE = "Generate Migrated Code"
    STEP_DESCRIPTION_GENERATE_CODE = (
        "Convert source files to target language, preserving existing target code "
        "and generating only new or missing files using knowledge base context"
    )
    AGENT_NAME = "Conversion Agent"
    AGENT_INSTRUCTIONS = (
        "Execute the conversion workflow to generate the migrated codebase. "
        "Existing target files are preserved automatically — only missing files are generated."
    )
    AGENT_DESCRIPTION = (
        "Converts source code to the target language using knowledge base context, "
        "preserving existing target code and matching its style."
    )
    # Logger messages
    LOG_FILLING_PROJECT_CODE = ("Filling project code | migration={migration}, source_path={source_path}, target_language={target_language}")
    LOG_TARGET_LANGUAGE_RESOLVED = ("✅ target_language resolved from DB {label} scanner_output: {target_language}")
    LOG_TARGET_LANGUAGE_RESOLVE_FAILED = ("Could not resolve target_language from scanner: {error}")
    LOG_SOURCE_SCANNER_NOT_FOUND = ("source scanner_output not found in DB — source lang will be unknown")
    LOG_TARGET_SCANNER_FALLBACK = ("⚠️ No target scanner_output in DB — target tech falls back to source")
    LOG_TECH_STACK_DETECTED = ("Tech stack detected | source_lang={source_lang}, target_framework={framework}")
    LOG_COPY_TARGET_PROJECT = ("🚀 STEP 1: Copying target project to migrated_code/...")
    LOG_TARGET_PROJECT_COPIED = ("✅ Target project copied: {files} files, {folders} folders")
    LOG_SKIP_TARGET_COPY = ("ℹ️ migrated_code/ already seeded — skipping target copy")
    LOG_NO_TARGET_PROJECT = ("ℹ️ No target project path found — generating files into empty migrated_code/")
    LOG_PROCESSING_NODE = "Processing: {goal_description}"
    LOG_GENERATING_FILE = "🆕 Generating: {node_name} (action={action})"
    LOG_CREATE_TEMPLATE = "[CREATE] Generating {node_name} via template"
    LOG_CONVERT_FILE = "[CONVERT] Converting {node_name} from {path}"
    LOG_FILE_CLASSIFIED = "File classified as: {file_type}"
    LOG_KB_GENERATION = "Attempting KB-based generation for {node_name}"
    LOG_TEMPLATE_FALLBACK = ("KB generation failed or unavailable, using template for {node_name}")
    LOG_ALL_STRATEGIES_FAILED = "❌ All strategies failed for {node_name}"
    LOG_FILE_CREATED = "✓ Created {node_name} ({strategy}, action={action})"
    LOG_FOLDER_CREATE_FAILED = "Failed to create folder {path}: {error}"
    LOG_FILE_GENERATION_ERROR = "❌ Error generating {node_name}: {error}"
    LOG_KB_LOAD_FAILED = "workflow event stream event failed (non-critical): {error}"
    LOG_GOALS_LOADED = "Loaded folder structure from DB"
    LOG_GOALS_STRUCTURE_WARNING = "Unexpected goals structure, processing as-is"
    LOG_COMPLETED_FLAGS_SAVED = ("✅ Updated isCompleted flags saved to folder_structure_with_goals (DB)")
    LOG_MIGRATION_SUMMARY = "Migration Completed Summary"
    LOG_FILL_PROJECT_CODE_ERROR = "Error in fill_project_code: {error}"
    LOG_PLACEHOLDER_CREATION_FAILED = "Failed to create placeholder: {error}"
    LOG_TARGET_PATH_EMPTY = "ℹ️ target_path exists but directory is empty or missing — skipping"
    LOG_TEMPLATE_EMPTY_CONTENT = "Template generation returned empty content for {node_name}"
    LOG_SOURCE_DIR_NOT_EXIST = "Source directory does not exist: {source_root}"
    LOG_SOURCE_PATH_NOT_DIRECTORY = "Source path is not a directory: {source_root}"
    LOG_COPY_DIRECTORY_TREE = "Copying directory tree from {source_root} to {dest_dir}"
    LOG_DIRECTORY_TREE_COPIED = "Directory tree copied: {files_copied} files, {folders_created} folders"
    LOG_COPYTREE_ERROR = "Error using copytree: {error}"
    LOG_COPY_DIRECTORY_ERROR = "Error copying directory tree: {error}"
    LOG_USING_LLM_CONVERSION_RULES = ("🤖 Using LLM to determine conversion rules for {source_lang} → {target_lang}")
    LOG_CONVERSION_RULES_RESULT = ("Conversion rules from LLM: source_port={source_port}, target_port={target_port}")
    LOG_LLM_CONVERSION_RULES_FAILED = ("LLM conversion rules failed: {error}")
    LOG_TECH_JSON_RULES_FAILED = ("Failed to get rules from tech JSON: {error}, using defaults" )
    LOG_CONVERSION_RULES_FAILED = ("Conversion rules failed: {error}")
    LOG_KB_NOT_FOUND = "KB not found at {uri_path}"
    LOG_KB_USING_EMBEDDER = "[KB LOAD] Using embedder: {embedder}"
    LOG_KB_LOADED = "KB loaded: {count} total vectors"
    LOG_KB_SOURCE_TARGET_COUNT = ("SOURCE: {source_count} vectors, TARGET: {target_count} vectors")
    LOG_KB_TABLE_NOT_FOUND = "KB table not found"
    LOG_KB_CONNECTION_NOT_INITIALIZED = "KB connection not initialized"
    LOG_KB_COUNT_CHECK_FAILED = "KB count check failed: {error}"
    LOG_KB_LOAD_FAILED = "Failed to load KB: {error}"
    LOG_EMPTY_SOURCE_FILE_PATH = "Empty source_file_path provided to _get_all_chunks_for_file"
    LOG_KB_SEARCH_FILE = "Searching KB for file:"
    LOG_KB_SEARCH_ORIGINAL_PATH = "Original path: {original_path}"
    LOG_KB_SEARCH_NORMALIZED_PATH = "Normalized path: {normalized_path}"
    LOG_KB_SEARCH_IS_TARGET = "is_target: {is_target}"
    LOG_KB_NO_CHUNKS_NORMALIZED = "No chunks found with normalized path, trying original path"
    LOG_KB_NO_CHUNKS_PATH_FILTER = "No chunks found with path filter, trying filename-based search"
    LOG_KB_FILENAME_MATCHES = "Filename search found {count} exact path matches"
    LOG_KB_RETRIEVED_AST_CHUNKS = "Retrieved {count} {project_type} AST chunks for {file_name}"
    LOG_KB_SAMPLE_CHUNK_PATH = "Sample chunk path from KB: {sample_path}"
    LOG_KB_NO_AST_CHUNKS = "No AST chunks found in KB for: {file_path}"
    LOG_KB_TRIED_NORMALIZED = "Tried normalized: {normalized_path}"
    LOG_KB_TRIED_ORIGINAL = "Tried original: {original_path}"
    LOG_KB_TRIED_FILENAME = "Tried filename: {file_name}"
    LOG_EMPTY_DEP_SOURCE_FILE_PATH = "Empty source_file_path provided to _get_dependency_chunks_for_file"
    LOG_SEARCH_DEP_CHUNKS = "Searching KB for dependency chunks:"
    LOG_DEP_ORIGINAL_PATH = "Original path: {original_path}"
    LOG_DEP_NORMALIZED_PATH = "Normalized path: {normalized_path}"
    LOG_DEP_IS_TARGET = "is_target: {is_target}"
    LOG_DEP_NO_CHUNKS_NORMALIZED = "No dependency chunks found with normalized path, trying original path"
    LOG_DEP_NO_CHUNKS_PATH_FILTER = "No dependency chunks found with path filter, trying filename-based search"
    LOG_DEP_FILENAME_MATCHES = "Filename search found {count} exact path matches"
    LOG_DEP_RETRIEVED_CHUNKS = "Retrieved {count} {project_type} dependency chunks for {file_name}"
    LOG_DEP_SAMPLE_CHUNK_PATH = "Sample dependency chunk path from KB: {sample_path}"
    LOG_DEP_NO_CHUNKS_FOUND = "No dependency chunks found in KB for: {file_path}"
    LOG_EMPTY_FILE_AND_CLASS = "Both source_file_path and class_name are empty"
    LOG_SEARCH_SEMANTIC_IR = ("Searching KB for semantic IR chunks: class={class_name!r} file={filename!r} (is_target={is_target})")
    LOG_SEMANTIC_CLASS_MATCH = "Found {count} chunks by class_name={class_name!r}"
    LOG_RETRIEVED_SEMANTIC_IR = ("Retrieved {count} {project_type} semantic IR chunks (class={class_name!r}, file={filename!r})")
    LOG_NO_AST_CHUNKS = "No AST chunks provided for {target_file_name}"
    LOG_USING_SOURCE_AST_CHUNKS = "Using {count} SOURCE AST chunks for {target_file_name}"
    LOG_USING_DEP_CHUNKS = "Using {count} dependency chunks for {target_file_name}"
    LOG_USING_SEM_IR_CHUNKS = "Using {count} semantic IR chunks for {target_file_name}"
    LOG_GENERATING_CODE_FROM_AST = "Generating {target_language} code from AST for {target_file_name}"
    LOG_CODE_GENERATED = "Code generated from AST: {length} chars"
    LOG_GENERATED_CODE_TOO_SHORT = "Generated code too short ({length} chars)"
    LOG_AST_GENERATION_FAILED = "AST generation failed for {target_file_name}: {error}"
    LOG_PINNED_DEPS_LOADED = "Loaded {count} pinned target deps for {file_name}"
    LOG_PINNED_DEPS_LOAD_FAILED = "Could not load pinned deps from target scanner: {error}"
    LOG_TEMPLATE_GENERATION_FAILED = "Template generation failed for {file_name} mode={mode}: {error}"
    LOG_FILENAME_DEPENDENCY_DETECTED = "Filename indicates dependency file: {file_name}"
    LOG_FILENAME_CONFIG_DETECTED = "Filename indicates config file: {file_name}"
    LOG_LLM_CLASSIFICATION_RESULT = "LLM classified as: {classification}"
    LOG_FILE_CLASSIFICATION_FAILED = "Classification failed: {error}"


