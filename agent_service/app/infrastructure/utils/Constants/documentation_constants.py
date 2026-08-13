class DocumentationLogMessages:
    TECH_DOC_CREATE_START = (
        "Creating technical documentation | migration={migration}, source_path={source_path}"
    )
    FUNC_DOC_CREATE_START = (
        "Creating functional documentation | migration={migration}, source_path={source_path}"
    )

    TECH_DOC_ALREADY_EXISTS = "✓ Technical documentation already created: {size} bytes"
    FUNC_DOC_ALREADY_EXISTS = "✓ Functional documentation already created: {size} bytes"

    TECH_DOC_SAVED = "✓ Technical documentation saved: {size} bytes"
    FUNC_DOC_SAVED = "✓ Functional documentation saved: {size} bytes"
    TECH_DOC_DIRECTORY = "Creating technical documentation in: {path}"
    FUNC_DOC_DIRECTORY = "Creating functional documentation in: {path}"
    SOURCE_PROJECT_UNDERSTANDING_EXISTS = (
        "✓ Source Project Understanding already created: {size} bytes"
    )
    GENERATING_SOURCE_PROJECT_UNDERSTANDING = (
        "Generating Source Project Understanding in: {path}"
    )
    PDF_GENERATED_SUCCESS = (
        "PDF generated successfully with automatic text wrapping and pagination."
    )
    SOURCE_PROJECT_UNDERSTANDING_CREATE_START = (
        "Creating Source Project Understanding document | migration={migration}, source_path={source_path}"
    )
    SOURCE_PROJECT_UNDERSTANDING_SAVED = (
        "✓ Source Project Understanding saved: {size} bytes"
    )
    PDF_GENERATION_ERROR = (
        "[Error:] Error creating pdf {file_name}, error: {error}"
    )
    SOURCE_PROJECT_UNDERSTANDING_ALREADY_EXISTS_LOG = (
        "Source Project Understanding document already exists"
    )
    SOURCE_PROJECT_UNDERSTANDING_START_LOG = (
        "Starting Source Project Understanding generation..."
    )
    SOURCE_PROJECT_UNDERSTANDING_GENERATED_LOG = (
        "Source Project Understanding document generated successfully"
    )
    SOURCE_PROJECT_UNDERSTANDING_SAVED_LOG = (
        "Source Project Understanding document saved successfully"
    )
    SERVER_BASE_FALLBACK_USED = (
        "SERVER_BASE_URL not configured. Falling back to default: {server_base}"
    )

    JSON_FILE_READ_ERROR = "Error reading JSON file {file_path}: {error}"
    TEXT_FILE_READ_ERROR = "Error reading text file {file_path}: {error}"


class DocumentationErrorMessages:
    AST_NOT_FOUND = (
        "Error: knowledge_graph.json not found at {path}. Run scanner agent first."
    )
    KG_NOT_FOUND = (
        "Error: knowledge_graph.json not found at {path}. Run scanner agent first."
    )

    RESPONSE_NOT_FOUND = (
        "Error: source_response.json not found at {path}. Run process_scanner_output_to_response first."
    )

    DESTINATION_NOT_FOUND = (
        "Error: Destination directory not found at {path}. Run scanner and response generation first."
    )

    TECH_DOC_SAVE_FAILED = (
        "Error: Failed to save technical documentation to {path}"
    )

    FUNC_DOC_SAVE_FAILED = (
        "Error: Failed to save functional documentation to {path}"
    )

    SOURCE_PROJECT_UNDERSTANDING_FAILED = (
        "Error generating Source Project Understanding: {error}"
    )

    SOURCE_PROJECT_UNDERSTANDING_SAVE_FAILED = (
        "Error: save failed at {path}"
    )


class DocumentationFileNames:
    TECH_MD = "technical_documentation.md"
    TECH_PDF = "technical_documentation.pdf"
    FUNC_MD = "functional_documentation.md"
    FUNC_PDF = "functional_documentation.pdf"
    SOURCE_PROJECT_UNDERSTANDING_MD = "source_project_understanding.md"
    SYNTACTIC_AST_JSON = "syntactic_ast.json"
    SCANNER_OUTPUT_JSON = "source_scanner_output.json"
    KNOWLEDGE_GRAPH_JSON = "knowledge_graph.json"
    RESPONSE_JSON = "source_response.json"


class DocumentationDataTypes:
    MARKDOWN = "markdown"
    PDF = "pdf"


class DocumentationEnvDefaults:
    SERVICE_HOST = "localhost"
    MIGRATION_PORT = "8003"
    SERVER_BASE_URL_TEMPLATE = "http://{host}:{port}"


class DocumentationSuccessMessages:
    TECH_DOC_ALREADY_CREATED = "✓ Technical documentation already created {path} ({size} bytes)"
    TECH_DOC_SAVED = "✓ Technical documentation saved to {path} ({size} bytes)"

    FUNC_DOC_ALREADY_CREATED = "✓ Functional documentation already created {path} ({size} bytes)"
    FUNC_DOC_SAVED = "✓ Functional documentation saved to {path} ({size} bytes)"

    SOURCE_PROJECT_UNDERSTANDING_ALREADY_CREATED = "✓ Source Project Understanding already created {path} ({size} bytes)"
    SOURCE_PROJECT_UNDERSTANDING_SAVED = "✓ Source Project Understanding saved to {path} ({size} bytes)"


class DocumentationStringLiterals:
    TEMP_FOLDER_NAME = "Temp"
    BACKSLASH_REPLACEMENT = "/"
    METADATA_TITLE = "# Source Project Understanding"
    METADATA_GENERATED_ON = "*Generated on: {timestamp}*"
    METADATA_SEPARATOR = "\n\n---\n\n"
