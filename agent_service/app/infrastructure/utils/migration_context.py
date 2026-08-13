from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

migration_id_ctx = ContextVar("migration_id")
# Optional coarse label for the current code path (e.g. migration:scanner_workflow, post_migration:pipeline)
# so LLM token rows get a useful prompt_name when agent.run() has no metadata.
llm_scope_ctx = ContextVar("llm_scope", default=None)

# One UUID per logical execution (re-run of same migration_name shares migration_id in DB;
# this distinguishes each run for token attribution).
migration_run_id_ctx = ContextVar("migration_run_id", default=None)
migration_name_ctx = ContextVar("migration_name")
migration_path_ctx = ContextVar("migration_path")
source_path_ctx = ContextVar("source_path")
target_language_ctx = ContextVar("target_language")
target_path_ctx = ContextVar("target_path")
description_ctx = ContextVar("description")
target_framework_ctx = ContextVar("target_framework")
target_architecture_ctx = ContextVar("target_architecture")
is_frontend_ctx = ContextVar("isFrontend")
target_frontend_ctx = ContextVar("target_frontend")
target_frontend_architecture_ctx =  ContextVar("target_frontend_architecture")
# framework_ctx = ContextVar("framework")
# architecture_ctx = ContextVar("architecture")
# build_tool_ctx = ContextVar("build_tool")
# database_ctx = ContextVar("database")

# Standard file extension for the target backend language (e.g., ".py", ".js") — LLM-detected.
target_file_ext_ctx = ContextVar("target_file_ext", default="")
# Standard file extension for the target frontend framework (e.g., ".vue", ".jsx") — LLM-detected.
target_frontend_file_ext_ctx = ContextVar("target_frontend_file_ext", default="")

# "code_migration" (default) or "unit_test_generation" — from description / detection.
execution_mode_ctx = ContextVar("execution_mode", default="code_migration")
# When execution_mode is unit_test_generation: free-form name of the test stack/tooling
# the user asked for (any string; may be empty — then prompts rely on the full description).
unit_test_framework_ctx = ContextVar("unit_test_framework", default=None)

# Same dict reference as agno Workflow session_state (for fields when contextvars do not propagate).
workflow_session_state_ctx = ContextVar("workflow_session_state", default=None)


@contextmanager
def llm_scope(name: str):
    """Set llm_scope_ctx for the duration of a migration/post-migration step (thread-safe for async)."""
    token = llm_scope_ctx.set(name)
    try:
        yield
    finally:
        llm_scope_ctx.reset(token)
