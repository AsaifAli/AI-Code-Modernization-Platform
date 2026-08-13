# File: application/app/infrastructure/utils/summarizer_utils.py

from pathlib import Path
from typing import Optional
import json
import logging
from agno.agent import Agent
from app.infrastructure.utils.user_context import current_user
from app.infrastructure.utils.file_utils import (
    get_migration_directory, 
    read_json_file, 
    read_file_content
)
from app.infrastructure.utils.agent_utils import runOptimizedPrompt
from app.infrastructure.utils.Constants.app_constants import MigrationScope
from app.infrastructure.repositories.detected_tech_summary_repository import (
    fetch_detected_tech_summary,
    set_detected_tech_summary,
)
from app.infrastructure.utils.Agent_helpers.Knowledge_base_helper import (
    kb_build_context,
    safe_json_dumps_limited,
)

logger = logging.getLogger(__name__)

def get_or_create_summarized_data(
    utility_agent: Agent,
    migration_name: str = "",
    source_path: str = "",
    data_type: str = "syntactic_ast",  # syntactic_ast | dependency_graph | detected_tech
    is_target: bool = False
) -> str:
    """
    Generic function to get or create summarized data from scanner_output.json.
    Language-agnostic and consolidated approach.
    
    Args:
        utility_agent: Agent for summarization
        migration_name: Migration project name
        source_path: Source code path
        data_type: Type of data to summarize (syntactic_ast | dependency_graph | detected_tech)
        is_target: If True, uses target_scanner_output.json
    
    Returns:
        str: Summarized content
    """
    user = current_user.get()
    try:
        migration_dir = get_migration_directory(migration_name=migration_name, source_path=source_path)
        resolved_migration_name = migration_name or migration_dir.name
        scope = MigrationScope.SCOPE_TARGET if is_target else MigrationScope.SCOPE_SOURCE
        
        # Determine file paths based on source/target
        prefix = "target" if is_target else "source"
        scanner_output_file = migration_dir / f"{prefix}_scanner_output.json"
        
        # Map data_type to scanner_output keys and cache file names
        data_mapping = {
            "syntactic_ast": {
                "key": "syntactic_ast",
                "cache_file": f"{prefix}_ast_summarized.txt"
            },
            "dependency_graph": {
                "key": "dependencies",  # dependencies are in scanner_output
                "cache_file": f"{prefix}_dependency_graph_summarized.txt"
            },
            "detected_tech": {
                "key": "tech_data",
                "cache_file": f"{prefix}_tech_summarized.txt"
            },
            "semantic_ir": {
                "key": "semantic_ir",
                "cache_file": f"{prefix}_semantic_ir_summarized.txt"
            },
            "complexity": {
                "key": "complexity_analysis",
                "cache_file": f"{prefix}_complexity_summarized.txt"
            }
        }
        
        if data_type not in data_mapping:
            logger.error(f"Invalid data_type: {data_type}")
            return ""
        
        mapping = data_mapping[data_type]
        cache_file_path = migration_dir / mapping["cache_file"]
        
        # DB cache for detected tech summary (string content), file cache for others.
        if data_type == "detected_tech":
            detected_tech_summary = fetch_detected_tech_summary(
                migration_name=resolved_migration_name,
                user_id=user.id,
                scope=scope,
            )
            if detected_tech_summary:
                logger.info("✓ Using cached detected tech summary from DB")
                return detected_tech_summary
        elif cache_file_path.exists():
            logger.info(f"✓ Using cached summary: {mapping['cache_file']}")
            return read_file_content(cache_file_path)
        
        # Read from consolidated scanner_output.json
        if not scanner_output_file.exists():
            logger.warning(f"{scanner_output_file.name} not found")
            return ""
        
        scanner_data = read_json_file(str(scanner_output_file))
        data_to_summarize = scanner_data.get(mapping["key"])
        
        if not data_to_summarize:
            logger.warning(f"No {data_type} found in {scanner_output_file.name}")
            return ""
        
        # Generate summary using LLM
        logger.info(f"Generating summary for {data_type}...")
        # IMPORTANT (syntactic_ast):
        # - Never pass full `syntactic_ast` into the LLM context. It can be huge and may include code snippets.
        # - Use KB chunk search as the scalable source of truth (KB indexing is lossless + chunked).
        # - If KB isn't built yet, fall back to summarizing only file paths (not AST bodies).
        payload_text = ""
        if data_type == "syntactic_ast":
            payload_text = kb_build_context(
                queries=[
                    "AST OVERVIEW",
                    "AST NODE",
                    "SOURCE FILE:",
                ],
                filters={"is_target": bool(is_target)},
                max_results_per_query=12,
                max_chars=14000,
            )
            if not payload_text:
                # Fallback: summarize only file paths, not the AST body.
                if isinstance(data_to_summarize, dict):
                    payload_text = safe_json_dumps_limited(
                        {"files": list(data_to_summarize.keys())},
                        max_chars=14000,
                    )
                else:
                    payload_text = safe_json_dumps_limited(
                        {"files": []},
                        max_chars=4000,
                    )
                
        else:
            # Non-AST types are typically much smaller; still keep a hard cap to be safe.
            payload_text = safe_json_dumps_limited(data_to_summarize, max_chars=14000)

        resp = runOptimizedPrompt(
            utility_agent,
            payload_text,
            use_summarizer=True
        )
        
        summarized_content = resp.content or ""
        # Cache the summary
        if summarized_content:
            if data_type == "detected_tech":
                row_id = set_detected_tech_summary(
                    migration_name=resolved_migration_name,
                    content=summarized_content,  # Save raw text directly as DB content.
                    user_id=user.id,
                    scope=scope,
                    save_artifact=True,
                )
                if row_id is not None:
                    logger.info("✓ Cached detected tech summary to DB")
                else:
                    logger.warning("Failed to cache detected tech summary in DB")
            else:
                cache_file_path.write_text(summarized_content, encoding="utf-8")
                logger.info(f"✓ Cached summary to: {mapping['cache_file']}")
        
        return summarized_content

    except Exception as e:
        logger.error(f"Error getting/creating summarized data: {e}")
        return ""


def getSummarizedSyntacticAst(
    utility_agent: Agent,
    migration_name: str = "",
    source_path: str = "",
    is_target: bool = False
) -> str:
    """
    Get summarized syntactic AST from scanner_output.json.
    
    Args:
        utility_agent: Agent for summarization
        migration_name: Migration project name
        source_path: Source code path
        is_target: If True, uses target_scanner_output.json
    
    Returns:
        str: Summarized AST content
    """
    return get_or_create_summarized_data(
        utility_agent=utility_agent,
        migration_name=migration_name,
        source_path=source_path,
        data_type="syntactic_ast",
        is_target=is_target
    )


def getSummarizedDependencyGraph(
    utility_agent: Agent,
    migration_name: str = "",
    source_path: str = "",
    is_target: bool = False
) -> str:
    """
    Get summarized dependency graph from scanner_output.json.
    
    Args:
        utility_agent: Agent for summarization
        migration_name: Migration project name
        source_path: Source code path
        is_target: If True, uses target_scanner_output.json
    
    Returns:
        str: Summarized dependency graph
    """
    return get_or_create_summarized_data(
        utility_agent=utility_agent,
        migration_name=migration_name,
        source_path=source_path,
        data_type="dependency_graph",
        is_target=is_target
    )


def getSummarizedDetectedTech(
    utility_agent: Agent,
    migration_name: str = "",
    source_path: str = "",
    is_target: bool = False
) -> str:
    """
    Get summarized tech stack from scanner_output.json.
    
    Args:
        utility_agent: Agent for summarization
        migration_name: Migration project name
        source_path: Source code path
        is_target: If True, uses target_scanner_output.json
    
    Returns:
        str: Summarized tech stack
    """
    return get_or_create_summarized_data(
        utility_agent=utility_agent,
        migration_name=migration_name,
        source_path=source_path,
        data_type="detected_tech",
        is_target=is_target
    )


def getSummarizedSemanticIR(
    utility_agent: Agent,
    migration_name: str = "",
    source_path: str = "",
    is_target: bool = False
) -> str:
    """
    Get summarized semantic IR from scanner_output.json.
    
    Args:
        utility_agent: Agent for summarization
        migration_name: Migration project name
        source_path: Source code path
        is_target: If True, uses target_scanner_output.json
    
    Returns:
        str: Summarized semantic IR
    """
    return get_or_create_summarized_data(
        utility_agent=utility_agent,
        migration_name=migration_name,
        source_path=source_path,
        data_type="semantic_ir",
        is_target=is_target
    )


def getSummarizedComplexity(
    utility_agent: Agent,
    migration_name: str = "",
    source_path: str = "",
    is_target: bool = False
) -> str:
    """
    Get summarized complexity analysis from scanner_output.json.
    
    Args:
        utility_agent: Agent for summarization
        migration_name: Migration project name
        source_path: Source code path
        is_target: If True, uses target_scanner_output.json
    
    Returns:
        str: Summarized complexity analysis
    """
    return get_or_create_summarized_data(
        utility_agent=utility_agent,
        migration_name=migration_name,
        source_path=source_path,
        data_type="complexity",
        is_target=is_target
    )


def clear_summary_cache(
    migration_name: str = "",
    source_path: str = "",
    data_type: Optional[str] = None,
    is_target: bool = False
) -> None:
    """
    Clear cached summary files.
    
    Args:
        migration_name: Migration project name
        source_path: Source code path
        data_type: Specific data type to clear, or None to clear all
        is_target: If True, clears target summaries
    """
    try:
        migration_dir = get_migration_directory(migration_name=migration_name, source_path=source_path)
        prefix = "target" if is_target else "source"
        
        if data_type:
            # Clear specific cache file
            data_mapping = {
                "syntactic_ast": f"{prefix}_ast_summarized.txt",
                "dependency_graph": f"{prefix}_dependency_graph_summarized.txt",
                "detected_tech": f"{prefix}_tech_summarized.txt",
                "semantic_ir": f"{prefix}_semantic_ir_summarized.txt",
                "complexity": f"{prefix}_complexity_summarized.txt"
            }
            
            cache_file = migration_dir / data_mapping.get(data_type, "")
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"✓ Cleared cache: {cache_file.name}")
        else:
            # Clear all cache files
            cache_patterns = [
                f"{prefix}_ast_summarized.txt",
                f"{prefix}_dependency_graph_summarized.txt",
                f"{prefix}_tech_summarized.txt",
                f"{prefix}_semantic_ir_summarized.txt",
                f"{prefix}_complexity_summarized.txt"
            ]
            
            for pattern in cache_patterns:
                cache_file = migration_dir / pattern
                if cache_file.exists():
                    cache_file.unlink()
                    logger.info(f"✓ Cleared cache: {cache_file.name}")
    
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")