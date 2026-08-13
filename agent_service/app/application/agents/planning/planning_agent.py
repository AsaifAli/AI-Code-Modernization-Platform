from agno.agent import Agent
from app.infrastructure.agents_backend.model_provider import model
# ─────────────────────────────────────────────────────────────────── Agents ────────────────────────────────────────────────────────────────
planning_agent = Agent(
    name="Planning Agent",
    model=model,
    markdown=False,
    description=(
        "Analyse source symbols: assign idiomatic target names, decide logical "
        "module grouping, and split large symbols into parts."
    ),
    instructions=[
        "You are a senior software migration architect.",
        "",
        "You will receive a batch of symbols belonging to one source module.",
        "For EVERY symbol output one JSON entry keyed by its exact symbol_id string.",
        "",
        "HARD CONSTRAINTS — violating any of these is an error:",
        "",
          "1. transformation",
        "   This field is pre-determined and passed to you per symbol.",
        "   parts[] for 1:1 symbols.",
        "   For Split: list of objects, each with these exact keys:",
        "   {part_id, target_symbol_name, target_symbol_type, start_line, end_line}",
        "   If parts is empty for a Split symbol, the entire response is considered invalid."
        "   Rules:",
        "   - part_id format: '<plan_id>_part_1', '<plan_id>_part_2', etc.",
        "   - start_line of first part MUST equal source_start of the symbol.",
        "   - end_line of last part MUST equal source_end of the symbol.",
        "   - Parts must be contiguous: part N end_line + 1 == part N+1 start_line.",
        "",
        "2. target_file",
        "   - MUST be a non-empty string with file extension.",
        "   - MUST use ONLY the target folder structure list provided in the context. Adhere strictly to the architecture.",
        "   - You CANNOT create new folders or modify the existing folder structure.",
        "   - Semantically analyze the symbol and assign it to the most appropriate existing folder.",
        "   - Path segments MUST be idiomatic for the target language.",
        "   - Related symbols should share the same target_file.",
        "",  
        "3. target_symbol_name",
        "   - MUST differ from the original symbol name.",
        "   - MUST be idiomatic for the target language and derived from the symbol's role and summary.",
        "",
        "4. target_symbol_type",
        "   One of: symbol | function | class | method | script ",
        "",
        "Module name is FINAL — do not change it.",
        "Output ONLY the raw JSON object. No explanation, no markdown fences.",
    ],
)

dependency_agent = Agent(
    model=model,
    markdown=False,
    debug_mode=True,
    instructions="""
    You are a dependency analysis agent. You will be given source code snippets
    from multiple files and their import/dependency declarations.

    Your job is to predict the target language dependency file.

    Rules:
    - Output ONLY a raw JSON object with exactly two fields: "filename" and "content".
    - "filename": correct dependency file for the target ecosystem
      (e.g. requirements.txt, package.json, pom.xml, go.mod, Gemfile, etc.)
    - "content": full file content as a string, correctly formatted for that ecosystem.
    - Include ONLY third-party packages — never stdlib modules.
    - Do not pin versions unless certain — use unpinned/latest format.
    - No explanations, no extra fields, no markdown.

    Example: {"filename": "dependency file.ext", "content": "library1\nlibrary2\n"}
    """
)