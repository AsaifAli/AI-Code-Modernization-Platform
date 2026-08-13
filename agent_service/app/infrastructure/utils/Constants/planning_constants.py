class PlanningLogMessages:

    FILE_MAPPING_EXISTS = (
        "⏭️ Skipped: file_mapping.json already exists at {path} ({count} mappings)"
    )
    FILE_MAPPING_CORRUPTED = (
        "Existing file_mapping.json is corrupted: {error}. Regenerating..."
    )
    FOLDER_STRUCTURE_EXISTS = (
        "⏭️ Skipped: folder_structure_with_goals.json already exists at {path}"
    )
    GENERATING_FOLDER_STRUCTURE = (
        "Generating folder_structure_with_goals.json at: {path}"
    )
    FOLDER_STRUCTURE_CREATED = (
        "✅ Successfully created folder_structure_with_goals.json at {path}"
    )
    FOLDER_STRUCTURE_CREATION_FAILED = (
        "❌ Failed to create folder_structure_with_goals.json at {path}"
    )

    FILE_MAPPING_EXISTS_DB = "file_mapping already exists in DB: {count} entries"
    FILE_MAPPING_SAVED_DB = "✅ File mapping saved to DB"
    FILE_MAPPING_STATS = "Mappings: {total}, Migrate: {migrate}, Preserve: {preserve}"
    SIM_SOURCE_FILE = "[SIM DEBUG] Source: {file}"
    SIM_MATCH_FILE = "[SIM DEBUG] Best match: {file}"
    SIM_COSINE_SCORE = "[SIM DEBUG] Cosine similarity: {score} (threshold: {threshold})"
    NO_SEMANTIC_SUMMARY_FOUND = (
        "No semantic_summary_ found in scanner outputs — all source files will be marked for conversion"
    )
    SOURCE_COMPLEXITY_EXISTS = "✅ Source complexity already calculated ({count} files)"
    COMPLEXITY_ANALYSIS_SAVED = "✅ Added complexity analysis to scanner_output.complexity_analysis (DB)"
    READING_TARGET_DATA = "Reading target data from: {file}"
    READING_SOURCE_FILE = "Reading from {file}"
    TARGET_SCANNER_KEYS = "Target scanner data keys: {keys}"
    TARGET_TOTAL_FILES = "Total files in target: {count}"
    LLM_FILE_CONTEXT = "LLM file context: {context}"
    FILE_MAPPING_LOADED_DB = "✅ File mapping loaded from DB ({count} mappings)"
    FOLDER_STRUCTURE_EXISTS_DB = "✓ folder_structure_with_goals already created in DB: {count} entries"
    TARGET_COMPLEXITY_PROCESSED = "✅ Processed {count} target files for complexity analysis"
    GENERATE_FILE_MAPPING_FAILED = "generate_file_mapping failed"
    CALCULATE_COMPLEX_SCORE_FAILED = "calculate_complex_score failed"
    FILEDATA_NONE = "fileData is None in {file}"
    FILEDATA_NOT_LIST = "fileData is not a list in {file}, it's: {type}"
    TOTAL_FILES_MISMATCH = "Mismatch: totalFiles={count} but fileData is empty!"
    CHECKING_ALTERNATE_FILE_LOCATION = "Checking if files are in a different location..."
    FILES_FOUND_IN_SYNTACTIC_AST = "Found {count} files in syntactic_ast, building fileData from it"
    FILE_ENTRIES_BUILT = "Built {count} file entries from syntactic_ast"
    TARGET_EMPTY_WARNING = "{file} contains no file data - target may be empty"
    PROCESSING_FILES_COMPLEXITY = "Processing {count} files for complexity analysis"
    CALCULATE_TARGET_COMPLEX_SCORE_FAILED = "calculate_target_complex_score failed"
    FULL_ERROR_DETAILS = "Full error details: {error}"
    TARGET_LANGUAGE_REHYDRATED = "Re-hydrated target_language from DB target scanner_output: {language}"
    FILE_MAPPING_DB_READ_FAILED = "File mapping exists but could not read from DB: {error}"
    PROMPT_GENERATED = "📝 Prompt generated: {count} chars"
    PROMPT_PREVIEW = "Prompt preview (first 1000 chars): {preview}"
    FILE_CONTEXT_LENGTH = "File context length: {count} chars"
    GENERATING_PROJECT_STRUCTURE = "🔄 Generating project structure with goals via LLM..."
    DEPENDENCY_FILE_TOO_SHORT = "Generated dependency file too short"
    DEPENDENCY_FILE_GENERATED = "✅ Successfully generated dependency file ({count} chars)"
    DEPENDENCY_FILE_FAILED = "Failed to generate dependency file: {error}"
    FOLDER_STRUCTURE_SAVED = "✅ Folder Structure saved: {file} with {count} children"
    PROJECT_STRUCTURE_ERROR = "Error generating project structure: {error}"