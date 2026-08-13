# app/infrastructure/utils/Constants/migration_constants.py

class MigrationConstants:

    # ------------------ ROOT KEYS ------------------
    TOTAL_FILES = "totalFiles"
    TOTAL_LOC = "total_lines_of_code"
    TOTAL_FUNCTIONS = "function_count"

    DETECTED_PRIMARY_LANGUAGE = "detected_primary_language"
    DETECTED_LANGUAGES = "detected_languages"
    DETECTED_DEPENDENCIES = "detected_depedencies"
    DETECTED_EXTENSIONS = "detected_extensions"

    TECH_STACK = "tech_stack"
    ARCHITECTURE = "architecture"
    ENTITY_DETECTED = "entityDetected"
    FILES = "files"
    CONFIG_FILES = "configurationFiles"
    NON_CONVERTIBLE_FILES = "nonConvertibleFiles"

    # ------------------ TECH STACK KEYS ------------------
    SOURCE_LANGUAGE = "sourceLanguage"
    TARGET_LANGUAGE = "targetLanguage"
    ORM_TECH = "ormTechnologie"
    DATABASE = "databaseName"
    BUILD_TOOL = "buildTool"

    # ------------------ ARCHITECTURE KEYS ------------------
    DETECT_ARCH = "detectArchitect"
    DEST_ARCH = "destinationArchitect"

    # ------------------ FILE KEYS ------------------
    FILE_NAME = "fileName"
    FILE_PATH = "filePath"
    FILE_TYPE = "fileType"
    FILE_SIZE = "fileSize"
    LINES_OF_CODE = "lineOfCode"
    FUNCTION_COUNT = "functionCount"

    # ------------------ SUMMARY SECTION ------------------
    SUMMARY_TITLE = "Migration Summary Overview"

    SUMMARY_ROOT = "summary"
    RECOMMENDATIONS_ROOT = "recommendations"
    TYPE = "type"
    TYPE_VALUE = "migration_summary"

    # ------------------ UI KEYS ------------------
    TITLE = "title"
    METRICS = "metrics"
    TECH_STACK_UI = "techStack"
    ARCHITECTURE_UI = "architecture"
    ENTITIES = "entities"
    NEXT_STEPS = "nextSteps"
    NOTES = "notes"
    AUTO_SELECTED = "autoSelected"
    TARGET_TECH_STACK = "targetTechStack"

    # ------------------ DEFAULT MESSAGES ------------------
    NEXT_STEPS_LIST = [
        "Customize tech stack",
        "Upload coding guidelines",
        "Proceed with migration"
    ]

    NOTES_LIST = [
        "You can keep the defaults or change them",
        "Upload coding standards for cleaner generated code",
        "Add custom instructions to guide conversion"
    ]

    # ------------------ KB / PLANNING / CONVERSION ------------------
    DOC_TYPE = "doc_type"
    DOC_TYPE_SOURCE_SYMBOL = "source_symbol"
    DOC_TYPE_SOURCE_DEPENDENCIES = "source_dependencies"
    DOC_TYPE_MIGRATED_CODE = "migrated_code"
    MIGRATION_STATUS = "migration_status"
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_ERROR = "error"
    SPLIT_TRANSFORMATION_MISSING_PARTS = "Split transformation missing parts from planning agent"
