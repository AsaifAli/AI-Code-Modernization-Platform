# KB Chunking Summary (Syntactic AST Context-Length Fix)

## Executive summary

We hit context-length limits because `scanner_output["syntactic_ast"]` can be extremely large and can include embedded code snippets (see `agent_service/Temp/syntactic_ast.json`).  
The fix is **not** to truncate AST at storage time, but to:

- **Store AST/code losslessly in the KB as chunks** (vector DB documents)
- **Retrieve only relevant chunks** for docs/diagrams/chat/conversion prompts (RAG-style), instead of embedding the full AST JSON into prompts

This keeps migration correctness (no code dropped) while scaling to large projects.

---

## What we store in KB (chunk types)

KB chunks are inserted into LanceDB via `KnowledgeBaseDB.add_ast_chunks()` in:

- `agent_service/app/infrastructure/utils/Agent_helpers/knowledge_base_helper.py`

Each stored KB document has:

- **`name`**: unique, includes `source_` or `target_` prefix
- **`text_content`**: the chunk payload (string)
- **`metadata`**: structured fields used for filtering / grouping

### Chunk types created for `syntactic_ast`

Per source file (`source_file_path`) we now store:

1) **File overview chunk** (`chunk_type="file_overview"`)
- Contains file header + semantic IR summary (if any)
- Intentionally lightweight (no full AST body here)

2) **Full AST JSON chunks** (`chunk_type="ast_json"`)
- Contains the **entire** AST JSON for that file, serialized as JSON
- If large, it is split into multiple parts using a text splitter
- **Lossless**: no truncation

3) **AST node chunks** (`chunk_type="ast_node"`)
- For each top-level AST child, store node JSON
- If a node is large, it is split into multiple parts (`node_chunk_index`)
- **Lossless**: no truncation

Additional KB content also exists:

- **Dependency chunks** (`chunk_type="dependency"`, `doc_type="dependency"`)
- **Semantic IR chunks** (`chunk_type="semantic_ir_overview" | "semantic_ir_detail"`)

---

## How we guarantee “no code missed”

### Storage-time rule (lossless)

We removed any AST body truncation and replaced it with **split-into-many-chunks** logic:

- The previous static truncation `[:8000]` was removed
- Large JSON blocks are split via `RecursiveCharacterTextSplitter`
- This ensures every character of AST/code content is stored somewhere in KB chunks

Key implementation (conceptual):

- Serialize full AST JSON for a file: `json.dumps(ast_data, ensure_ascii=False, default=str)`
- Split into parts via `_split_text_for_kb(...)`
- Store each part as its own KB document (`chunk_type="ast_json"`)

### Prompt-time rule (bounded context)

When building prompts for LLM calls, we **do not** embed full AST.  
Instead, we use KB retrieval helpers that enforce a max output size (character budget). This is safe because it affects only prompt context, not stored data.

---

## How we identify “which chunks belong to which file”

Every file-derived KB chunk includes metadata like:

- `source_file_path`
- `file_name`
- `file_directory`
- `is_target` (SOURCE vs TARGET)
- `chunk_type` (`file_overview`, `ast_json`, `ast_node`, etc.)
- ordering helpers:
  - `chunk_index`
  - for split nodes: `node_index`, `node_chunk_index`
  - for split AST JSON: `ast_part_index`

This lets the system:

- filter all chunks for a specific file (`source_file_path` / `file_name`)
- retrieve only SOURCE or only TARGET (`is_target`)
- reconstruct multi-part chunks (using indexes)

---

## How downstream agents use KB instead of full `syntactic_ast`

### Diagram generation

`diagram_helper._load_scanner_data()` now prefers KB retrieval (`kb_build_context`) and only falls back to a **strictly capped** JSON view if KB is missing.

### Documentation (Source Project Understanding)

`getSourceProjectUnderstandingPrompt()` replaces `scanner_output["syntactic_ast"]` with:

- `"<omitted: stored as KB chunks>"`

and injects KB-derived context blocks.

### Summaries

`summary_manager.get_or_create_summarized_data(..., data_type="syntactic_ast")` no longer summarizes the full AST payload.  
It uses KB retrieval; if KB is missing, it summarizes only file paths.

### Conversion

Conversion already uses KB retrieval per file:

- `_get_all_chunks_for_file(...)`
- `_get_dependency_chunks_for_file(...)`
- `_get_semantic_ir_chunks_for_file(...)`

and then generates code from the retrieved chunks (never passes whole `syntactic_ast`).

### Chatbot

We added a KB-backed chat tool/agent that answers questions via KB search:

- global questions: `kb_build_context(...)`
- file-scoped questions: `kb_build_file_context(...)`

---

## What a chunk “looks like” (examples)

### Example: `file_overview` chunk (payload)

```
PROJECT TYPE: SOURCE
SOURCE FILE: path/to/file.pm
FILE NAME: file.pm
FILE DIRECTORY: path/to
ARTIFACT TYPE: syntactic_ast
FILE OVERVIEW:
SEMANTIC IR:
Class Foo: utility_class; methods=3, properties=2
```

### Example: `ast_json` chunk (payload)

```
PROJECT TYPE: SOURCE
SOURCE FILE: path/to/file.pm
...
AST JSON (FULL, CHUNKED):
{
  "ast": {
    "type": "...",
    ...
  },
  "language": "perl",
  "code": "...."   // if present in AST artifact
}
```

### Example: `ast_node` chunk (payload)

```
PROJECT TYPE: SOURCE
SOURCE FILE: path/to/file.pm
AST NODE 12: function_definition
NODE NAME: process_payment
NODE CHUNK: 0
{
  "type": "function_definition",
  ...
}
```

---

## Operational note: KB is built immediately after scan

To minimize latency and ensure all later steps can use KB retrieval, KB indexing is triggered right after scanning:

- After `run_project_scanner()` saves `scanner_output`
- After `scan_target_project()` completes

Failures in KB build are logged as **non-fatal** so scanning remains reliable; KB can be rebuilt later via the KB agent if needed.

