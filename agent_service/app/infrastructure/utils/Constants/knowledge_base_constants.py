class KnowledgeBaseConstants :
    LOG_AST_CHUNKS_ADDED = "Successfully added {count} {project_type} AST chunks to KB"

    LOG_AST_CHUNKS_ADD_FAILED = "Failed to add AST chunks to KB: {error}"

    LOG_METADATA_CHUNK_FETCH_FAILED = "get_chunks_by_metadata: {error}"

    LOG_NO_SEMANTIC_IR_FOUND = "No semantic_ir list found or it is empty"

    LOG_SEMANTIC_IR_PROCESSED = (
        "Processed {entry_count} semantic IR entries → {chunk_count} chunks ({project_type})"
    )

    LOG_KB_BUILD_START = "Building KB DB | migration=%s, source_path=%s, include_target=%s"

    # CACHE
    LOG_KB_USING_CACHE = "Using cached KB table"

    # PHASE LOGS
    LOG_PHASE_SOURCE_AST = "PHASE 1: Processing SOURCE AST..."
    LOG_PHASE_TARGET_AST = "PHASE 2: Processing TARGET AST..."
    LOG_PHASE_VERIFY = "PHASE 3: Verifying KB..."

    # SOURCE PROCESSING
    LOG_SOURCE_AST_CHUNKS = "✅ SOURCE AST: %s chunks from %s"
    LOG_SOURCE_AST_EMPTY = "SOURCE AST file empty or invalid JSON"
    LOG_SOURCE_AST_ERROR = "Error processing SOURCE AST: %s"
    LOG_SOURCE_AST_NOT_FOUND = "No SOURCE AST file (source_scanner_output.json)"

    LOG_SOURCE_DEP_CHUNKS = "✅ SOURCE DEPENDENCIES: %s chunks from %s"
    LOG_SOURCE_DEP_ERROR = "Error processing SOURCE dependencies: %s"

    LOG_SOURCE_SEM_CHUNKS = "✅ SOURCE SEMANTIC IR: %s chunks"
    LOG_SOURCE_SEM_ERROR = "Error processing SOURCE semantic IR: %s"

    # TARGET PROCESSING
    LOG_TARGET_AST_CHUNKS = "✅ TARGET AST: %s chunks from %s"
    LOG_TARGET_AST_EMPTY = "TARGET AST file empty or invalid JSON"
    LOG_TARGET_AST_ERROR = "Error processing TARGET AST: %s"
    LOG_TARGET_AST_NOT_FOUND = "No TARGET AST file found (target_scanner_output.json)"

    LOG_TARGET_DEP_CHUNKS = "✅ TARGET DEPENDENCIES: %s chunks from %s"
    LOG_TARGET_DEP_ERROR = "Error processing TARGET dependencies: %s"

    LOG_TARGET_SEM_CHUNKS = "✅ TARGET SEMANTIC IR: %s chunks"
    LOG_TARGET_SEM_ERROR = "Error processing TARGET semantic IR: %s"

    # KB TEST
    LOG_KB_TOTAL_DOCS = "KB Test - Total documents: %s"
    LOG_KB_SOURCE_DOCS = "KB Test - SOURCE documents: %s"
    LOG_KB_TARGET_DOCS = "KB Test - TARGET documents: %s"

    LOG_KB_ZERO_RESULTS = "⚠️ KB search returned 0 results!"
    LOG_KB_SEARCH_SUCCESS = "✅ KB search working: %s total results"
    LOG_KB_SEARCH_FAILED = "❌ KB search test failed: %s"

    # FINAL ERROR
    LOG_KB_BUILD_ERROR = "Error building KB: %s"