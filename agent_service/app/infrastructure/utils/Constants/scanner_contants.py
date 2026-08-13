class ScannerConstants:

    PROCESSING_SCANNER_OUTPUT = (
        "Processing scanner output | migration={migration}, target_path={target_path}"
    )
    GENERATING_TARGET_RESPONSE_JSON = "Generating enhanced target_response.json..."
    GENERATING_TARGET_RESPONSE_EVENT = "Generating enhanced target_response.json ..."
    TARGET_SCANNER_OUTPUT_NOT_FOUND = (
        "Error: target_scanner_output.json not found. Run scan_target_project first."
    )
    TARGET_RESPONSE_ALREADY_EXISTS_LOG = (
        "Target response.json already exists, skipping regeneration"
    )
    TARGET_RESPONSE_ALREADY_EXISTS = (
        "✅ Target response already exists: {file} ({size} bytes)"
    )
    TARGET_RESPONSE_ALREADY_GENERATED_RETURN = "✅ target_response.json already generated ({size} bytes). Skipping to save tokens."
    TARGET_RESPONSE_FILE_READ_WARNING = (
        "Target response file exists but could not read: {error}"
    )
    TARGET_PROJECT_SIZE = (
        "Target project size: {files} files, {size_mb:.2f} MB ({category})"
    )
    EXTRACTED_TARGET_ENTITIES = "Extracted {count} entities from target project"
    DETECTED_CONFIG_FILES = "Detected {count} configuration files"
    DETECTING_DATABASE_LOG = "Detecting database in target project..."
    DETECTING_DATABASE_STEP = "Detecting database configuration in target project..."
    DETECTED_DATABASE = "Detected database: {database}"
    RUNNING_RULE_BASED_ANALYSIS = "Running rule-based analysis for target project..."
    RUNNING_LLM_ANALYSIS = "Running LLM analysis on target project structure..."
    LLM_ANALYSIS_COMPLETED = "LLM analysis completed"
    GENERATED_TARGET_RESPONSE_JSON = "Generated target_response.json → {file}"
    TARGET_ANALYSIS_SUCCESS_SUMMARY = (
        "Target enhanced analysis created: "
        "Files={files}, "
        "Language={language}, "
        "Framework={framework}, "
        "Database={database}, "
        "Entities={entities}"
    )
    TARGET_ANALYSIS_RETURN_MESSAGE = (
        "✅ Target enhanced analysis created\n"
        " • File: {file}\n"
        " • Files analyzed: {files}\n"
        " • Language: {language}\n"
        " • Framework: {framework}\n"
        " • Database: {database}\n"
        " • Entities detected: {entities}\n"
        "Next step: You can now compare source vs target or start planning."
    )
    USER_CONTEXT_NOT_AVAILABLE = "Error: User context not available"
    TARGET_PROJECT_DATA_FOUND = (
        "Target project data found - including in source_response.json"
    )
    ERROR_PREFIX = "Error: {error}"
    TARGET_RESPONSE_GENERATION_FAILED = "Target response generation failed: {error}"
    PROCESSING_SCANNER_OUTPUT_SOURCE = (
        "Processing scanner output | migration={migration}, source_path={source_path}"
    )
    SKIP_CONFIG_DETECTION = (
        "source_path is '{source_path}', skipping config file detection"
    )
    CONFIG_DETECTION_FAILED = (
        "Error detecting config files: {error}, continuing with Step 3 logs"
    )
    DETECTING_DATABASE = "Detecting database with web search..."
    GENERATING_SCANNER_RESPONSE = "Scanner response generating"
    SOURCE_RESPONSE_GENERATED = (
        "Generated enhanced source_response.json with intelligent LLM analysis"
    )
    ERROR_GENERATING_RESPONSE = "Error generating enhanced response: {error}"
    ERROR_IN_RUN_PROJECT_SCANNER = "Error in run_project_scanner"
    USER_CONTEXT_NOT_AVAILABLE = "Error: User context not available"
    STEP_ERROR_SEND_FAILED = "Failed to send step_error event: {error}"
    NO_TARGET_PATH = "No target project path provided"
    NO_TARGET_PATH_SKIP_SCAN = "No target project path provided - skipping target scan"
    TARGET_PATH_NOT_FOUND = "Target path does not exist: {path}"
    ERROR_TARGET_PATH_NOT_FOUND = "Error: Target path does not exist: {path}"
    TARGET_PATH_NOT_DIRECTORY = "Target path is not a directory: {path}"
    ERROR_TARGET_PATH_NOT_DIRECTORY = "Error: Target path is not a directory: {path}"
    TARGET_DIRECTORY_EMPTY = "Target directory is empty: {path}"
    TARGET_DIRECTORY_EMPTY_SKIP = "Target directory is empty - skipping target scan"
    SCANNING_TARGET_PROJECT = "Scanning target project at: {path}"
    EMPTY_TARGET_SCAN_OUTPUT = "process_project_folder returned empty output"
    ERROR_EMPTY_TARGET_SCAN = "Error: Target scan returned empty output"
    INVALID_TARGET_OUTPUT_TYPE = "process_project_folder returned non-dict: {type}"
    ERROR_INVALID_TARGET_TYPE = "Error: Target scan returned invalid type: {type}"
    EMPTY_SYNTACTIC_AST = "Target scan produced empty syntactic_ast"
    TARGET_OUTPUT_KEYS = "Target output keys: {keys}"
    TARGET_AST_FILES_FOUND = "Target scan found {count} files in syntactic_ast"
    TARGET_FILES_FOUND = "Found {count} files in target project"
    AUTO_SET_TARGET_LANGUAGE = (
        "Auto-setting target language from target scan: {language}"
    )
    TARGET_LANGUAGE_SET = "Target language set to: {language}"
    AUTO_DETECTED_TARGET_LANGUAGE = "Auto-detected target language: {language}"
    TARGET_LANGUAGE_ALREADY_SET = "Target language already set to: {language}"
    TARGET_LANGUAGE_MISMATCH = (
        "Target language mismatch: context={context}, detected={detected}"
    )
    TARGET_ALREADY_SCANNED = "Target already scanned: {file} ({size} bytes)"
    TARGET_SCANNER_FILE_WARNING = (
        "Target scanner file exists but could not read size: {error}"
    )
    TARGET_OUTPUT_EMPTY_SAVE = (
        "target_output is empty - cannot save target_scanner_output.json"
    )
    TARGET_SCANNER_OUTPUT_SAVED = "Saved target_scanner_output.json with {count} files"
    TARGET_SERIALIZATION_ERROR = "Error serializing target_output: {error}"
    ERROR_SAVING_TARGET_OUTPUT = "Error saving target scanner output: {error}"
    TARGET_SCAN_SUCCESS_SUMMARY = (
        "Target project scanned successfully: "
        "Language={language}, Framework={framework}, Files={files}"
    )

    TARGET_SCAN_RETURN_MESSAGE = (
        "Target project scanned and analyzed!\n"
        "  • Language: {language}\n"
        "  • Framework: {framework}\n"
        "  • Files: {files}\n"
        "  • Target files will be preserved during code generation\n\n"
        "NEXT: System will use file mapping to preserve existing target code"
    )
    ERROR_SCANNING_TARGET_PROJECT = "Error scanning target project: {error}"
    ERROR_SENDING_STEP_LOGS = (
        "Error sending Step 2/3 logs when response exists: {error}"
    )
    PROJECT_SIZE_INFO = "Project size: {files} files, {size_mb:.2f} MB ({category})"
    RESPONSE_DB_SAVE_FAILED = "Failed to save response.json to DB (normalized): %s"
    STEP_ERROR_EVENT_FAILED = "Failed to send step_error event: {error}"
    SOURCE_SCANNER_OUTPUT_NOT_FOUND = (
        "Error: source_scanner_output not found. Run scanner first."
    )
    PROCESSING_TARGET_SCANNER_OUTPUT = (
        "Processing scanner output | migration={migration}, target_path={target_path}"
    )
    EMPTY_TARGET_OUTPUT_SAVE = (
        "target_output is empty - cannot save target_scanner_output.json"
    )
    WARNING_EMPTY_SYNTACTIC_AST = "Warning: Target scan produced empty syntactic AST"
    TARGET_OUTPUT_SAVED = "Saved target_scanner_output.json with {count} files"
    TARGET_LANGUAGE_MISMATCH_WARNING = (
        "Warning: Target language mismatch - context={context}, detected={detected}"
    )
    TARGET_LANGUAGE_MISMATCH_BLOCK = (
        "❌ Target language mismatch: Expected {expected}, "
        "but detected {detected}. "
        "Migration cannot proceed with incompatible target language."
    )
    TARGET_ALREADY_SCANNED_RETURN = "✅ Target project already scanned. File: {file} ({size} bytes). Skipping re-scan to save tokens."
    ERROR_EMPTY_TARGET_OUTPUT = "Error: Target scan produced empty output"
    TARGET_SCAN_FAILED_RESULT = "Target scan failed: {error}"
    STARTING_SCAN = "Starting scan of: {path}"
    STARTING_OPTIMIZED_SCAN = "Starting optimized scan with LLM pre-filtering: {path}"
    CACHED_SCANNER_OUTPUT_LOAD_FAILED = (
        "Could not load scanner output for cached result: {error}"
    )
    EARLY_LANGUAGE_DETECTION_FAILED = (
        "Could not load scanner output for early language detection: {error}"
    )
    SCANNER_DB_SAVE_FAILED = "Failed to save scanner_output to DB artifact: %s"
    CLASS_INSTANCE_TO_DICT_WARNING = (
        "Converting class instance {type} to dict for JSON serialization"
    )
    TYPE_TO_STRING_WARNING = "Converting {type} to string for JSON serialization"
    LOC_COUNT_FAILED = "Failed to count LOC for {file_path}: {error}"
    DEPENDENCY_EXTRACTION_ERROR = "Error extracting dependencies from AST: {error}"
    DEPENDENCY_EXTRACTION_AGENT_ROLE = (
        "You are a dependency extraction expert for {language}."
    )
    DEPENDENCY_EXTRACTION_INPUT = (
        "Extract all dependencies from {language} AST for {source_file}"
    )
    CHECK_COMPLETION_STATUS_FAILED = "Failed to check completion status: {error}"
    LLM_LIBRARY_EXTRACTION_FAILED = "LLM library extraction failed: {error}"
    USING_CACHED_SEMANTIC_SUMMARY = "Using cached semantic summary for {scan_type}"
    SKIPPING_AST_SUMMARY_ERROR = "Skipping AST summary for {filepath}: AST has error"
    LLM_SEMANTIC_SUMMARY_FAILED = "LLM semantic summary failed for {filepath}: {error}"
    GENERATED_SEMANTIC_SUMMARY_CACHE = "Generated semantic summary cache"
    LLM_RESPONSE_PARSING_FAILED = "LLM response parsing failed: {error}"
    ENHANCED_RESPONSE_SUCCESS_MESSAGE = (
        "Enhanced Response JSON generated with Web Search!\n\n"
        "Analysis Results:\n"
        "  • Source Language: {source_language}\n"
        "  • Architecture: {architecture}\n"
        "  • Framework: {framework} {framework_version}\n"
        "  • Database: {database}\n\n"
        "Statistics:\n"
        "  • Total Files: {total_files}\n"
        "  • Entities: {entities}\n"
        "  • Non-convertible: {non_convertible}\n\n"
        "Saved to: {response_file}"
    )
    PROJECT_METRICS_CALCULATION_FAILED = "Error calculating project metrics: {error}"
    PROJECT_METRICS_INFO = (
        "Project metrics: {total_files} files, {total_size_mb:.2f} MB"
    )
    CONFIG_LIMITS_DEBUG = "Config limits: max_files={max_files}, max_chars={max_chars}"
    EXISTING_RESPONSE_MESSAGE = (
        " Enhanced Response JSON was already created, which is used to return the data!\n\n"
        " Analysis Results:\n"
        "  • Source Language: {source_language}\n"
        "  • Current Architecture: {architecture}\n"
        "  • Framework: {framework}\n"
        "  • Build Tool: {build_tool}\n"
        "  • Database: {database}\n\n"
        " Project Statistics:\n"
        "  • Total Files: {total_files}\n"
        "  • Entities Detected: {entities}\n"
        "  • Configuration Files: {config_files}\n"
        "  • Non-convertible Files: {non_convertible}\n\n"
    )
    LLM_RESPONSE_PARSING_FAILED = "LLM response parsing failed: {error}"
    EXTRACT_ENTITIES_PROMPT_RENDERED = "extract_entities_prompt fetched and rendered successfully. Preview: {preview}..."
    LLM_ENTITY_EXTRACTION_FAILED = "Error extracting entities with LLM: {error}"
    EMPTY_SEMANTIC_IR_WARNING = "Empty semantic IR provided"
    USING_LLM_ENTITY_EXTRACTION = "Using LLM for entity extraction"
    BATCH_NO_JSON_ARRAY = "Batch {batch_num}: No JSON array found in response"
    BATCH_NO_CLOSING_BRACKET = "Batch {batch_num}: No closing bracket found"
    BATCH_SEMANTIC_ENTRIES_EXTRACTED = (
        "Batch {batch_num}: Extracted {count} semantic entries"
    )
    BATCH_EXPECTED_LIST_WARNING = "Batch {batch_num}: Expected list, got {type}"
    BATCH_JSON_PARSE_ERROR = "Batch {batch_num}: JSON parse error → {error}"
    BATCH_PROCESSING_FAILED = "Batch {batch_num} failed: {error}"
    PROCESSING_TOTAL_BATCHES = (
        "Processing {total_batches} batches (batch size: {batch_size})"
    )
    PROCESSING_BATCH_ITEMS = (
        "Batch {batch_num}/{total_batches}: Processing {items} items..."
    )
    BATCH_FAILED = "Batch {batch_num} failed: {error}"
    SEMANTIC_IR_ANALYZING_FILES = "Semantic IR: Analyzing {file_count} files"
    SEMANTIC_IR_ITEMS_FOUND = (
        "Semantic IR: Found {item_count} classes/functions to analyze"
    )
    SEMANTIC_IR_NO_DATA_WARNING = "No semantic IR generated, creating placeholder"
    SEMANTIC_IR_COMPLETE = "Semantic IR Complete: {entry_count} total entries"
    CACHED_OUTPUT_MESSAGE = (
        "Returning already created files!\n\n"
        "Files saved:\n"
        "  • {scanner_output} (contains syntactic_ast, semantic_ir, tech_data, dependency_graph)\n"
    )
    SCAN_COMPLETE_LOG = "Scan complete:"
    SCAN_STAT_SYNTACTIC = "  - Syntactic AST: {count} files"
    SCAN_STAT_SEMANTIC = "  - Semantic IR: {count} entries"
    SCAN_STAT_NON_CONVERTIBLE = "  - Excluded: {count} non-convertible files"
    SCAN_STAT_LANGUAGE = "  - Language: {language}"
    OPTIMIZED_SCANNER_SUCCESS = (
        "Optimized scanner completed with LLM pre-filtering!\n\n"
        "Results:\n"
        "  • Syntactic AST: {syntactic_count} files\n"
        "  • Semantic IR: {semantic_count} entries\n"
        "  • Excluded: {non_convertible_count} non-convertible files\n"
        "  • Language: {language}\n"
        "  • Framework: {framework}\n\n"
        "All files saved to: {migration_dir}"
    )
    RULE_BASED_PREFILTER_EXCLUDED = "Rule-based pre-filter: {count} files excluded"
    LLM_WEBSEARCH_EXCLUDED = "LLM + Web Search excluded {count} additional files"
    LLM_ANALYSIS_FAILED = "LLM analysis failed: {error}"
    USING_RULE_BASED_RESULTS_ONLY = "Using rule-based results only"
    DETECTING_NON_CONVERTIBLE_FILES = "Detecting non-convertible files..."
    ERROR_LISTING_FILES = "Error listing files: {error}"
    NO_FILES_FOUND = "No files found in project"
    ALL_FILES_FILTERED_BY_RULES = "All files filtered by rules"
    RUNNING_LLM_ANALYSIS = (
        "Running LLM analysis with web search for {file_count} files..."
    )
    TOTAL_EXCLUDED_FILES = "Total excluded: {count} files"
    SAMPLE_EXCLUDED_FILES = "Sample excluded files:"
    SAMPLE_EXCLUDED_FILE_ITEM = "   • {file}"
    DETECTED_LANGUAGE = "Detected language: {file_path} → {lang}"
    LANGUAGE_DETECTION_FAILED = "Language detection failed for {file_path}: {error}"
    PACKAGE_FILE_OVERSIZED = (
        "Skipping oversized package file: {filename} ({size_mb:.2f} MB)"
    )
    PACKAGE_FILE_TRUNCATED = "Truncated {filename} at {max_chars} chars"
    PACKAGE_FILE_READ = "Read {filename} ({chars} chars)"
    PACKAGE_FILES_SUMMARY = (
        "Package files: {file_count} files, {total_chars} total chars"
    )
    PACKAGE_FILE_READ_ERROR = "Could not read {filename}: {error}"
