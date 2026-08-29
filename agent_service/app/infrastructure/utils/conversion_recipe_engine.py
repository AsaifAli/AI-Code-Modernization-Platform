"""Deterministic conversion hygiene and syntax-aware target validation."""
from __future__ import annotations
from dataclasses import dataclass
import ast
from functools import lru_cache
import re

@dataclass(frozen=True)
class RecipeContext:
    source_language: str
    target_language: str
    target_framework: str = ""
    target_architecture: str = ""

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    available: bool
    language: str
    diagnostics: tuple[str, ...] = ()
    validator: str = "none"

_ALIASES={"js":"javascript","javascript":"javascript","ts":"typescript","typescript":"typescript","tsx":"tsx","py":"python","python":"python","java":"java","go":"go","golang":"go","php":"php","cs":"c_sharp","c#":"c_sharp","csharp":"c_sharp","dotnet":"c_sharp"}

def _language_name(language:str)->str:
    return _ALIASES.get((language or "").strip().lower(), (language or "").strip().lower())

def sanitize_generated_code(code:str)->str:
    if not code: return ""
    code=code.replace("\ufeff","").replace("\r\n","\n").replace("\r","\n")
    m=re.fullmatch(r"\s*```[^\n]*\n(?P<body>.*)\n```\s*",code,re.DOTALL)
    if m: code=m.group("body")
    lines=[line.rstrip() for line in code.split("\n")]
    return "\n".join(lines).strip() + ("\n" if code.strip() else "")

def build_conversion_rules(context:RecipeContext)->str:
    target=_language_name(context.target_language)
    rules=[
      "Preserve externally observable behavior, data flow, side effects, and error semantics.",
      "Prefer target-language idioms over transliterating source syntax.",
      "Reuse approved dependencies; do not invent packages merely to make the translation convenient.",
      "Preserve public names/interfaces unless the migration plan explicitly changes them.",
      "Keep generated code self-contained for the requested symbol and respect the target file/module layout.",
      "Do not emit markdown, prose, placeholders, TODOs, or pseudocode.",
    ]
    if target in {"javascript","typescript","tsx"}: rules += ["Use one consistent ESM/CommonJS convention from the target project.","Preserve async/Promise and error propagation semantics."]
    elif target=="python": rules += ["Use standard Python imports and preserve sync/async behavior.","Do not replace real errors with placeholder returns."]
    elif target=="java": rules += ["Respect Java visibility, checked exceptions, packages, and target project conventions.","Do not synthesize main unless the source execution contract requires it."]
    elif target=="go": rules += ["Use idiomatic Go error returns and package declarations.","Do not introduce concurrency without source-behavior justification."]
    elif target=="php": rules += ["Preserve namespaces/imports and target-project typing conventions."]
    elif target=="c_sharp": rules += ["Preserve .NET async/await, nullable behavior, and namespace/type conventions."]
    return "\n".join([f"TARGET LANGUAGE: {context.target_language or 'unknown'}",f"TARGET FRAMEWORK: {context.target_framework or 'framework not specified'}",f"TARGET ARCHITECTURE: {context.target_architecture or 'architecture not specified'}","DETERMINISTIC CONVERSION RULES:"]+[f"- {x}" for x in rules])

@lru_cache(maxsize=16)
def _parser(language:str):
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser(language)
    except Exception:
        return None

def _ts_validate(code:str, language:str)->ValidationResult:
    parser=_parser(language)
    if parser is None: return ValidationResult(False,False,language,(),"tree-sitter")
    try:
        tree=parser.parse(code.encode("utf-8"))
        root=tree.root_node
        if not root.has_error(): return ValidationResult(True,True,language,(),"tree-sitter")
        return ValidationResult(False,True,language,(),"tree-sitter")
    except Exception as exc:
        return ValidationResult(False,True,language,(f"parser error: {exc}",),"tree-sitter")

def validate_target_fragment(code:str, language:str)->ValidationResult:
    normalized=sanitize_generated_code(code); lang=_language_name(language)
    if not normalized: return ValidationResult(False,True,lang,("generated code is empty",),"deterministic")
    if lang=="python":
        try: ast.parse(normalized); return ValidationResult(True,True,lang,(),"python-ast")
        except SyntaxError as exc: return ValidationResult(False,True,lang,(f"SyntaxError line {exc.lineno}: {exc.msg}",),"python-ast")
    candidate=normalized
    if lang=="go" and not re.search(r"^\s*package\s+\w+",candidate): candidate="package main\n\n"+candidate
    elif lang=="java" and not re.search(r"\bclass\s+[A-Za-z_$][\w$]*",candidate): candidate="class __MigrationFragment {\n"+candidate+"\n}\n"
    elif lang=="c_sharp" and not re.search(r"\b(?:class|struct|interface|record)\s+[A-Za-z_][\w]*",candidate): candidate="class __MigrationFragment {\n"+candidate+"\n}\n"
    elif lang=="php" and not candidate.lstrip().startswith("<?php"): candidate="<?php\n"+candidate+"\n"
    return _ts_validate(candidate,lang)

def format_validation_feedback(result:ValidationResult)->str:
    return "\n".join([f"validator={result.validator}",f"language={result.language}",f"available={str(result.available).lower()}",f"valid={str(result.valid).lower()}"]+[f"diagnostic={x}" for x in result.diagnostics[:5]])
