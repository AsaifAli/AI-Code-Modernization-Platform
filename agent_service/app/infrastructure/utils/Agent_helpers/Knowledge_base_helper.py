import os
import json
import logging
from typing import List
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.infrastructure.agents_backend.qdrant_knowledge import QdrantKnowledgeBase, _collection_name
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
__all__ = [
    '_process_ast_for_kb',
    '_process_dependencies_for_kb',
    '_process_semantic_ir_for_kb',       # ADD THIS
    'get_prompt_manager_instance',
    'kb_build_context',
    'kb_build_file_context',
    'safe_json_dumps_limited',
    '_create_file_specific_chunks',
    '_create_semantic_ir_chunks',        # ADD THIS
    'flatten_json',
]
# ------------------------------ File Utils ------------------------------
class KnowledgeBaseDB:
    """Persistent remote knowledge base backed by Qdrant Cloud.

    The public surface intentionally matches the previous vector-store helper so
    the agent/tool layer does not need to know which vector store is used.
    """

    def __init__(self):
        self.source = QdrantKnowledgeBase(_collection_name("source"))
        self.target = QdrantKnowledgeBase(_collection_name("target"))
        # Existing callers use ``self.kb`` for the currently active mixed KB.
        self.kb = self.source

    def _select_kb(self, is_target: bool = False) -> QdrantKnowledgeBase:
        return self.target if is_target else self.source

    def add_ast_chunks(self, chunks: List[dict], ast_artifact_path: str) -> int:
        if not chunks:
            return 0

        def normalize_path_for_kb(path: str) -> str:
            return str(Path(path).as_posix()) if path else ""

        contents = []
        for i, ch in enumerate(chunks):
            c = ch.get("content", "")
            md = dict(ch.get("metadata") or {})
            if not c:
                continue

            md["source"] = normalize_path_for_kb(ast_artifact_path)
            fn = md.get("file_name", Path(md.get("source_file_path", "")).name or "unknown")
            idx = md.get("chunk_index", i)
            ct = md.get("chunk_type", "chunk")
            target_prefix = "target_" if md.get("is_target", False) else "source_"
            unique_name = f"{target_prefix}{fn}_chunk_{idx}_{ct}"

            contents.append({"name": unique_name, "text_content": c, "metadata": md})

        if not contents:
            return 0

        kb = self.target if contents[0]["metadata"].get("is_target") else self.source
        try:
            inserted = kb.insert_many(contents)
            project_type = "TARGET" if contents[0]["metadata"].get("is_target") else "SOURCE"
            logger.info("Successfully added %s %s AST chunks to Qdrant", inserted, project_type)
            return inserted
        except Exception as exc:
            logger.error("Failed to add AST chunks to Qdrant: %s", exc, exc_info=True)
            raise

    def isFilePresent(self, file_name: str) -> bool:
        for kb in (self.source, self.target):
            if kb.scroll(filters={"source": file_name}, limit=1):
                return True
        return False

    def get_chunks_by_metadata(self, filters: dict, limit: int = 1000) -> List[dict]:
        out = []
        for kb in (self.source, self.target):
            for payload in kb.scroll(filters=filters, limit=limit):
                md = payload.get("metadata") or {}
                out.append({
                    "content": (payload.get("text_content") or payload.get("content") or "")[:200],
                    "meta_data": md,
                })
                if len(out) >= limit:
                    return out
        return out


_instance = None

def get_prompt_manager_instance():
    global _instance
    if _instance is None:
        _instance = KnowledgeBaseDB()
    return _instance

def flatten_json(data, prefix=""):
    """Recursively flatten JSON into key-path → value text pairs."""
    items = []
    if isinstance(data, dict):
        for k, v in data.items():
            new_prefix = f"{prefix}.{k}" if prefix else k
            items.extend(flatten_json(v, new_prefix))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            new_prefix = f"{prefix}[{i}]"
            items.extend(flatten_json(v, new_prefix))
    else:
        # Create readable descriptive text
        text = f"{prefix}: {data}"
        items.append(text)
    return items
# ----------------------------
# KB Retrieval helpers (prompt-safe)
# ----------------------------
def safe_json_dumps_limited(obj, *, max_chars: int = 12000) -> str:
    """
    JSON stringify with a hard character cap.
    Prevents context-length explosions when large artifacts are present.
    Language-agnostic (works for any scanner output shape).
    """
    try:
        s = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except Exception:
        try:
            s = str(obj)
        except Exception:
            s = "<unserializable>"
    if max_chars and len(s) > max_chars:
        return s[: max_chars - 200] + "\n... <truncated> ..."
    return s
def _extract_search_text(item) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for k in ("text_content", "content", "text", "page_content"):
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                return v
        payload = item.get("payload")
        if isinstance(payload, str):
            return payload
    return str(item)
def kb_build_context(
    *,
    queries: List[str],
    filters: dict | None = None,
    max_results_per_query: int = 8,
    max_chars: int = 14000,
) -> str:
    """
    Build a compact context string from KB results (chunk-based).
    RATIONALE (syntactic_ast):
    - Full `syntactic_ast` can contain large embedded code snippets (see Temp syntactic_ast.json).
    - We must NOT pass that entire payload into LLM prompts (context-length + cost).
    - Instead we store AST/code losslessly in KB chunks and retrieve only the relevant pieces.
    Works globally: filters + semantic search, no language-specific checks.
    """
    if not queries:
        return ""
    kb = get_prompt_manager_instance().kb
    parts: List[str] = []
    used = 0
    for q in queries:
        if used >= max_chars:
            break
        try:
            # agno Knowledge supports search with query + filters; signature varies by version,
            # so we attempt both common parameter names.
            try:
                results = kb.search(query=q, max_results=max_results_per_query, filters=filters or {})
            except TypeError:
                results = kb.search(query=q, limit=max_results_per_query, filters=filters or {})
        except Exception:
            results = []
        if not results:
            continue
        parts.append(f"## KB results for query: {q}\n")
        for r in results:
            txt = _extract_search_text(r).strip()
            if not txt:
                continue
            remaining = max_chars - used
            if remaining <= 0:
                break
            if len(txt) > remaining:
                txt = txt[: max(0, remaining - 80)] + "\n... <truncated> ..."
            parts.append(txt)
            parts.append("\n")
            used += len(txt) + 1
    return "\n".join(parts).strip()
def kb_build_file_context(
    *,
    question: str,
    source_file_path: str,
    is_target: bool = False,
    max_results: int = 30,
    max_chars: int = 16000,
) -> str:
    """
    Build KB context scoped to ONE file (handles split chunks).
    Tries multiple matching strategies (normalized path, original path, filename)
    without language-specific logic.
    """
    if not question or not source_file_path:
        return ""
    kb = get_prompt_manager_instance().kb
    normalized_path = str(source_file_path).replace("\\", "/")
    original_path = str(source_file_path)
    filename = Path(source_file_path).name
    attempts = [
        (normalized_path, {"source_file_path": normalized_path, "is_target": is_target}),
        (original_path, {"source_file_path": original_path, "is_target": is_target}),
        (filename, {"file_name": filename, "is_target": is_target}),
    ]
    parts: List[str] = [f"## KB file-scoped context\nFILE: {source_file_path}\nQUESTION: {question}\n"]
    used = len(parts[0])
    seen = set()
    for q, f in attempts:
        if used >= max_chars:
            break
        try:
            try:
                results = kb.search(query=question, max_results=max_results, filters=f)
            except TypeError:
                results = kb.search(query=question, limit=max_results, filters=f)
        except Exception:
            results = []
        for r in results:
            txt = _extract_search_text(r).strip()
            if not txt:
                continue
            key = txt[:200]
            if key in seen:
                continue
            seen.add(key)
            remaining = max_chars - used
            if remaining <= 0:
                break
            if len(txt) > remaining:
                txt = txt[: max(0, remaining - 80)] + "\n... <truncated> ..."
            parts.append(txt)
            parts.append("\n")
            used += len(txt) + 1
    return "\n".join(parts).strip()
# ----------------------------
# CHUNKING STRATEGY
# ----------------------------
splitter = RecursiveCharacterTextSplitter(
    separators=["\n", " ", ".", ",", ";", ":"],
)
def _split_text_for_kb(text: str, *, chunk_size: int = 6000, chunk_overlap: int = 200) -> List[str]:
    """
    Split large text into multiple chunks WITHOUT losing content.
    This is used for KB storage (not prompt-time truncation).
    RATIONALE (syntactic_ast):
    - KB indexing must be LOSSLESS: never truncate AST/code when persisting to KB.
    - Chunking provides scalability while keeping per-chunk size manageable.
    """
    if not text:
        return []
    try:
        local_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n", " ", ".", ",", ";", ":"],
        )
        docs = local_splitter.create_documents([text])
        return [d.page_content for d in docs if getattr(d, "page_content", "").strip()]
    except Exception:
        # Fallback: naive slicing (still lossless, just less semantic)
        out = []
        i = 0
        while i < len(text):
            out.append(text[i : i + chunk_size])
            i += max(1, chunk_size - chunk_overlap)
        return [s for s in out if s.strip()]
def _build_semantic_summary(semantic_ir: list, source_file_path: str) -> str:
    """
    Build semantic summary string for a specific file from class-wise semantic IR.
    Matches entries by file path, then formats each class entry.
    Language-agnostic. Supports SOURCE and TARGET.
    """
    if not semantic_ir:
        return "No semantic IR data available."
    if isinstance(semantic_ir, dict):
        semantic_ir = semantic_ir.get("semantic_ir", [])
    if not isinstance(semantic_ir, list):
        return f"Invalid semantic IR: {type(semantic_ir).__name__}"
    norm = source_file_path.replace("\\", "/")
    entries = [
        e for e in semantic_ir
        if isinstance(e, dict) and e.get("file", "").replace("\\", "/") == norm
    ]
    if not entries:
        return f"No semantic IR for: {source_file_path}"
    parts = []
    for e in entries:
        cls_name   = e.get("class") or "(file-level)"
        role       = e.get("role", "?")
        methods    = e.get("methods", []) or []
        properties = e.get("properties", []) or []
        parts.append(
            f"Class {cls_name}: {role}; "
            f"methods={len(methods)}, properties={len(properties)}"
        )
    return "\n".join(parts) if parts else "No entities."
def _create_file_specific_chunks(
    source_file_path: str,
    ast_data: dict,
    semantic_ir: list,
    artifact_type: str,
    is_target: bool = False
) -> List[dict]:
    """
    Create file-aware AST chunks with semantic IR context.
    Language-agnostic - works for any programming language.
    Supports BOTH SOURCE and TARGET projects.
    
    Args:
        source_file_path: Path to the source file
        ast_data: AST data for the file
        semantic_ir: Semantic IR data
        artifact_type: Type of artifact (e.g., "syntactic_ast")
        is_target: Whether this is from TARGET project (default False = SOURCE)
    """
    chunks = []
    file_name = Path(source_file_path).name
    file_dir = Path(source_file_path).parent.as_posix()
    
    project_type = "TARGET" if is_target else "SOURCE"
    
    header = (
        f"PROJECT TYPE: {project_type}\n"
        f"SOURCE FILE: {source_file_path}\n"
        f"FILE NAME: {file_name}\n"
        f"FILE DIRECTORY: {file_dir}\n"
        f"ARTIFACT TYPE: {artifact_type}\n"
    )
    
    summary = _build_semantic_summary(semantic_ir, source_file_path)
    
    # CHUNK 0: File Overview (NO AST body here; keep it lightweight)
    chunks.append({
        "content": (
            header +
            f"FILE OVERVIEW:\n"
            f"SEMANTIC IR:\n{summary}\n"
        ),
        "metadata": {
            "source_file_path": source_file_path,
            "file_name": file_name,
            "file_directory": file_dir,
            "artifact_type": artifact_type,
            "chunk_type": "file_overview",
            "chunk_index": 0,
            "is_syntactic_ast": True,
            "has_semantic_ir": bool(summary and "No semantic" not in summary),
            "is_target": is_target,  # CRITICAL: Tag SOURCE vs TARGET
        },
    })
    # CHUNK(S): Full AST JSON (lossless, split into multiple chunks)
    try:
        ast_json = json.dumps(ast_data, indent=2, ensure_ascii=False, default=str)
    except Exception:
        ast_json = str(ast_data)
    for part_idx, part in enumerate(_split_text_for_kb(ast_json), start=1):
        chunks.append({
            "content": (
                header
                + "AST JSON (FULL, CHUNKED):\n"
                + part
            ),
            "metadata": {
                "source_file_path": source_file_path,
                "file_name": file_name,
                "file_directory": file_dir,
                "artifact_type": artifact_type,
                "chunk_type": "ast_json",
                "chunk_index": len(chunks),
                "ast_part_index": part_idx,
                "is_syntactic_ast": True,
                "is_target": is_target,
            },
        })
    
    SKIP_TYPES = {"comment", "whitespace", "newline", "punctuation", "line_ending"}
    ast_node = ast_data.get("ast") or {}
    for i, child in enumerate(ast_node.get("children") or []):
        if child.get("type") in SKIP_TYPES:
            continue
        node_name = "unknown"
        for c in (child.get("children") or []):
            if isinstance(c, dict) and c.get("type") == "identifier":
                node_name = c.get("value", "unknown")
                break
        
        try:
            child_json = json.dumps(child, indent=2, ensure_ascii=False, default=str)
        except Exception:
            child_json = str(child)
        for sub_idx, sub_part in enumerate(_split_text_for_kb(child_json), start=0):
            chunks.append({
                "content": (
                    header +
                    f"AST NODE {i}: {child.get('type')}\n"
                    f"NODE NAME: {node_name}\n"
                    f"NODE CHUNK: {sub_idx}\n"
                    f"{sub_part}"
                ),
                "metadata": {
                    "source_file_path": source_file_path,
                    "file_name": file_name,
                    "file_directory": file_dir,
                    "artifact_type": artifact_type,
                    "chunk_type": "ast_node",
                    "node_type": child.get("type"),
                    "node_name": node_name,
                    "node_index": i,
                    "node_chunk_index": sub_idx,
                    "chunk_index": len(chunks),
                    "is_syntactic_ast": True,
                    "is_target": is_target,
                },
            })
    
    return chunks
def _process_ast_for_kb(ast_data: dict, is_target: bool = False) -> List[dict]:
    """
    Process AST data into KB-ready chunks.
    Language-agnostic implementation.
    Supports BOTH SOURCE and TARGET projects.
    
    Args:
        ast_data: AST data from source_scanner_output.json
        is_target: Whether this is TARGET project (default False = SOURCE)
    
    Returns:
        List of chunk dicts ready for KB insertion
    """
    syn = ast_data.get("syntactic_ast", ast_data if isinstance(ast_data, dict) else {})
    sem = ast_data.get("semantic_ir", [])
    
    if not isinstance(syn, dict):
        return []
    
    chunks = []
    artifact_type = "target_syntactic_ast" if is_target else "syntactic_ast"
    
    for source_path, file_ast in syn.items():
        file_chunks = _create_file_specific_chunks(
            source_path,
            file_ast,
            sem,
            artifact_type,
            is_target=is_target
        )
        chunks.extend(file_chunks)
    
    return chunks
def _process_dependencies_for_kb(all_dependencies: list, is_target: bool = False) -> List[dict]:
    """
    Process dependencies data into KB-ready chunks.
    Each dependency in the deps array becomes a separate chunk.
    
    Args:
        all_dependencies: List of dependency objects with format:
            [{"file_path": "...", "deps": [{"module_name": "...", ...}, ...]}, ...]
        is_target: Whether this is TARGET project (default False = SOURCE)
    
    Returns:
        List of chunk dicts ready for KB insertion
    """
    if not isinstance(all_dependencies, list):
        return []
    
    chunks = []
    project_type = "TARGET" if is_target else "SOURCE"
    artifact_type = "target_dependencies" if is_target else "dependencies"
    
    for dep_obj in all_dependencies:
        if not isinstance(dep_obj, dict) or "file_path" not in dep_obj:
            continue
        
        file_path = str(dep_obj.get("file_path", "")).strip()
        deps_list = dep_obj.get("deps", [])
        
        if not file_path or not deps_list:
            continue
        
        file_name = Path(file_path).name
        file_dir = Path(file_path).parent.as_posix()
        
        # Create a chunk for each dependency in the deps array
        for idx, dep in enumerate(deps_list):
            if not isinstance(dep, dict) or "module_name" not in dep:
                continue
            
            module_name = dep.get("module_name", "")
            import_type = dep.get("import_type", "unknown")
            import_suffix = dep.get("import_suffix", "")
            import_path = dep.get("import_path", "")
            
            if not module_name:
                continue
            
            # Create content for the dependency chunk
            content = (
                f"PROJECT TYPE: {project_type}\n"
                f"SOURCE FILE: {file_path}\n"
                f"FILE NAME: {file_name}\n"
                f"FILE DIRECTORY: {file_dir}\n"
                f"ARTIFACT TYPE: {artifact_type}\n"
                f"\nDEPENDENCY:\n"
                f"Module Name: {module_name}\n"
                f"Import Type: {import_type}\n"
                f"Import Suffix: {import_suffix}\n"
                f"Import Path: {import_path}\n"
            )
            
            # Create metadata
            metadata = {
                "source_file_path": file_path,
                "file_name": file_name,
                "file_directory": file_dir,
                "artifact_type": artifact_type,
                "doc_type": "dependency",
                "chunk_type": "dependency",
                "chunk_index": idx,
                "module_name": module_name,
                "import_type": import_type,
                "import_suffix": import_suffix,
                "import_path": import_path,
                "is_target": is_target,
            }
            
            chunks.append({
                "content": content,
                "metadata": metadata
            })
    
    return chunks
def _create_semantic_ir_chunks(
    file_entry: dict,
    artifact_type: str,
    is_target: bool = False
) -> List[dict]:
    """
    Create KB-ready chunks from ONE class-wise semantic IR entry.
    Each entry produces:
      - 1 overview chunk  (class name, role, method/property summary, dependencies)
      - 1 detail chunk    (full method signatures with params+actions, properties with types)
    Entry schema:
        {
          "class": "ClassName or null",
          "role": "utility_class",
          "confidence": "high",
          "reasoning": "...",
          "file": "path/to/file.ext",
          "language": "Perl",
          "dependencies": [...],
          "properties": [{"name":..., "type":..., "role":...}],
          "methods":     [{"name":..., "role":..., "params":[...], "actions":[...]}]
        }
    """
    chunks = []
    if not isinstance(file_entry, dict):
        return chunks
    file_path = str(file_entry.get("file", "")).strip()
    if not file_path:
        return chunks
    file_name    = Path(file_path).name
    file_dir     = Path(file_path).parent.as_posix()
    project_type = "TARGET" if is_target else "SOURCE"
    class_name   = file_entry.get("class") or "(file-level)"
    role         = file_entry.get("role", "unknown")
    language     = file_entry.get("language", "unknown")
    confidence   = file_entry.get("confidence", "")
    reasoning    = file_entry.get("reasoning", "")
    dependencies = file_entry.get("dependencies", []) or []
    methods      = file_entry.get("methods", []) or []
    properties   = file_entry.get("properties", []) or []
    header = (
        f"PROJECT TYPE: {project_type}\n"
        f"SOURCE FILE: {file_path}\n"
        f"FILE NAME: {file_name}\n"
        f"FILE DIRECTORY: {file_dir}\n"
        f"CLASS: {class_name}\n"
        f"LANGUAGE: {language}\n"
        f"ROLE: {role}\n"
        f"ARTIFACT TYPE: {artifact_type}\n"
    )
    base_metadata = {
        "source_file_path": file_path,
        "file_name":        file_name,
        "file_directory":   file_dir,
        "class_name":       class_name,     # primary migration unit key
        "role":             role,
        "language":         language,
        "artifact_type":    artifact_type,
        "is_semantic_ir":   True,
        "is_target":        is_target,
    }
    # ── CHUNK 0: Class overview ───────────────────────────────────────────
    m_names = [
        m.get("name", "?") if isinstance(m, dict) else str(m)
        for m in methods
    ]
    p_names = [
        p.get("name", "?") if isinstance(p, dict) else str(p)
        for p in properties
    ]
    deps_str = ", ".join(str(d) for d in dependencies) if dependencies else "none"
    overview_content = (
        header
        + f"CLASS OVERVIEW (SEMANTIC IR):\n"
        f"Reasoning: {reasoning}\n"
        f"Confidence: {confidence}\n"
        f"Methods ({len(methods)}): {', '.join(m_names) or 'none'}\n"
        f"Properties ({len(properties)}): {', '.join(p_names) or 'none'}\n"
        f"Dependencies: {deps_str}\n"
    )
    chunks.append({
        "content": overview_content,
        "metadata": {
            **base_metadata,
            "chunk_type":      "semantic_ir_overview",
            "chunk_index":     0,
            "method_count":    len(methods),
            "property_count":  len(properties),
        }
    })
    # ── CHUNK 1: Methods + Properties detail ─────────────────────────────
    if methods or properties:
        method_lines = []
        for m in methods:
            if isinstance(m, dict):
                name    = m.get("name", "?")
                mrole   = m.get("role", "")
                params  = ", ".join(m.get("params", []))
                actions = "; ".join(m.get("actions", []))
                method_lines.append(
                    f"  - {name}({params})"
                    + (f" [{mrole}]" if mrole else "")
                    + (f" → {actions}" if actions else "")
                )
            else:
                method_lines.append(f"  - {m}")
        prop_lines = []
        for p in properties:
            if isinstance(p, dict):
                pname = p.get("name", "?")
                ptype = p.get("type", "")
                prole = p.get("role", "")
                prop_lines.append(
                    f"  - {pname}"
                    + (f": {ptype}" if ptype else "")
                    + (f" [{prole}]" if prole else "")
                )
            else:
                prop_lines.append(f"  - {p}")
        detail_content = (
            header
            + f"METHODS ({len(methods)}):\n"
            + ("\n".join(method_lines) or "  none") + "\n"
            + f"PROPERTIES ({len(properties)}):\n"
            + ("\n".join(prop_lines) or "  none") + "\n"
        )
        chunks.append({
            "content": detail_content,
            "metadata": {
                **base_metadata,
                "chunk_type":     "semantic_ir_detail",
                "chunk_index":    1,
                "method_names":   m_names,
                "method_count":   len(methods),
                "property_count": len(properties),
            }
        })
    return chunks
def _process_semantic_ir_for_kb(ast_data: dict, is_target: bool = False) -> List[dict]:
    """
    Process semantic_ir list from scanner output into KB-ready chunks.
    Language-agnostic. Supports SOURCE and TARGET projects.
    semantic_ir is a list of file entries (NOT keyed by file path like syntactic_ast).
    Each entry has: file, file_role, classes, standalone_functions, dependencies, language.
    Args:
        ast_data: Full scanner output dict containing "semantic_ir" key
        is_target: Whether this is TARGET project
    Returns:
        List of chunk dicts ready for KB insertion
    """
    semantic_ir = ast_data.get("semantic_ir", [])
    if not isinstance(semantic_ir, list) or not semantic_ir:
        logger.warning("No semantic_ir list found or it is empty")
        return []
    artifact_type = "target_semantic_ir" if is_target else "semantic_ir"
    chunks = []
    for file_entry in semantic_ir:
        file_chunks = _create_semantic_ir_chunks(
            file_entry=file_entry,
            artifact_type=artifact_type,
            is_target=is_target,
        )
        chunks.extend(file_chunks)
    logger.info(
        f"Processed {len(semantic_ir)} semantic IR entries → "
        f"{len(chunks)} chunks ({'TARGET' if is_target else 'SOURCE'})"
    )
    return chunks