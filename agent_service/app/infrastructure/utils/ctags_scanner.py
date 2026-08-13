"""
Language-agnostic project graph generator.

parse  — Universal Ctags → definitions + imports + calls (~150 languages)

Call graph, inheritance, and dependencies are all
derived from ctags reference tags with upgraded field extraction.

"""

from __future__ import annotations
import hashlib
import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
import ast as _ast

from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)

__all__ = [
    '_build_files_payload_relative',
    '_remap_paths',
    '_build_calls_from_ctags',
    '_build_inheritance_deps',
    '_import_tag_to_dep',
    '_tag_to_symbol',
    '_patch_end_lines',
    '_build_file_index',
    '_enrich_calls_by_language',
    '_enrich_calls_for_files',
    '_enrich_symbols_by_language',
    '_CALL_ENRICHERS',
    '_SYMBOL_ENRICHERS',
    '_extract_perl_imports',
    '_enrich_perl_params',
    '_enrich_perl_exports',
    '_enrich_perl_calls',
    '_enrich_js_exports',
    '_enrich_python_access',
    '_enrich_go_access',
    '_detect_perl_test_framework',
    '_FRAMEWORK_PATTERNS',
    '_FILE_DEP_ENRICHERS',
    '_enrich_file_deps_by_language',
    '_extract_python_imports',
    '_extract_js_imports',
]



# ============================================================================
# 1.  Kind map  (unchanged — normalises ctags kind strings)
# ============================================================================

_KIND_MAP: Dict[str, str] = {
    "function":       "function",
    "method":         "method",
    "subroutine":     "function",
    "procedure":      "function",
    "routine":        "function",
    "func":           "function",
    "subprogram":     "function",
    "generator":      "function",
    "coroutine":      "function",
    "macro":          "variable",
    "decorator":      "function",
    "lambda":         "function",
    "class":          "class",
    "struct":         "class",
    "record":         "class",
    "union":          "class",
    "object":         "class",
    "implementation": "class",
    "category":       "class",
    "interface":      "interface",
    "trait":          "interface",
    "protocol":       "interface",
    "mixin":          "interface",
    "typeclass":      "interface",
    "enum":           "enum",
    "enumerator":     "enum",
    "enumconstant":   "enum",
    "variable":       "variable",
    "local":          "variable",
    "constant":       "variable",
    "define":         "variable",
    "parameter":      "variable",
    "property":       "field",
    "field":          "field",
    "member":         "field",
    "attribute":      "field",
    "slot":           "field",
    "ivar":           "field",
    "typedef":        "type_alias",
    "type":           "type_alias",
    "alias":          "type_alias",
    "typealias":      "type_alias",
    "newtype":        "type_alias",
    "namespace":      "namespace",
    "module":         "module",
    "package":        "module",
    "submodule":      "module",
    "section":        "module",
    "header":         "module",
    "annotation":     "type_alias",
    "event":          "field",
    "delegate":       "type_alias",
    "exception":      "class",
}

_SKIP_KINDS = {
    "file", "filename", "unknown", "anchor",
    "chunk", "foreign", "externvar", "label",
}


def _build_files_payload_relative(
    file_paths: List[Path],
    source_root: Optional[Path],
) -> Tuple[List[dict], Dict[str, str]]:
    files = []
    name_to_abs: Dict[str, str] = {}

    for fp in file_paths:
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
            if source_root:
                try:
                    rel = str(fp.relative_to(source_root)).replace("\\", "/")
                except ValueError:
                    rel = fp.name
            else:
                rel = fp.name

            files.append({"name": rel, "content": content})
            name_to_abs[rel]     = str(fp.resolve())   # relative key
            name_to_abs[fp.name] = str(fp.resolve())   # ← basename fallback key

        except Exception as e:
            logger.warning(f"Could not read {fp}: {e}")

    return files, name_to_abs


def _remap_paths(tags: List[dict], name_to_abs: Dict[str, str]) -> List[dict]:
    """
    Map service-returned paths back to absolute local paths.
    Tries three strategies in order:
      1. Exact match on relative key  (e.g. "src/utils.cpp")
      2. Normalised separators match  (e.g. "src\\utils.cpp" → "src/utils.cpp")
      3. Basename match fallback      (e.g. "utils.cpp")
    """
    basename_to_abs: Dict[str, str] = {
        Path(abs_path).name: abs_path
        for abs_path in name_to_abs.values()
    }

    for tag in tags:
        fname = tag.get("path", "")
        if not fname:
            continue

        if fname in name_to_abs:
            tag["path"] = name_to_abs[fname]
        elif fname.replace("\\", "/") in name_to_abs:
            tag["path"] = name_to_abs[fname.replace("\\", "/")]
        else:
            basename = Path(fname).name
            if basename in basename_to_abs:
                tag["path"] = basename_to_abs[basename]

    return tags


# ============================================================================
# 3.  Signature parsers  (unchanged)
# ============================================================================

def _split_on_commas(sig: str) -> List[str]:
    sig = sig.strip()
    if sig.startswith("(") and sig.endswith(")"):
        sig = sig[1:-1]
    if not sig or sig.strip() == "void":
        return []
    parts: List[str] = []
    depth = 0
    buf:   List[str] = []
    for ch in sig + ",":
        if ch in "(<[{":    depth += 1
        elif ch in ")>]}":  depth -= 1
        if ch == "," and depth == 0:
            t = "".join(buf).strip()
            if t: parts.append(t)
            buf = []
        else:
            buf.append(ch)
    return parts


def _generic_param_parser(sig: str) -> List[dict]:
    result = []
    for raw in _split_on_commas(sig):
        raw = raw.strip()
        if not raw:
            continue
        default: Optional[str] = None
        if "=" in raw:
            head, _, tail = raw.partition("=")
            raw, default  = head.strip(), tail.strip()
        if ":" in raw:
            name_part, _, type_part = raw.partition(":")
            result.append({
                "name":    name_part.strip().lstrip("*&").split()[-1],
                "type":    type_part.strip() or None,
                "default": default,
            })
            continue
        tokens = raw.split()
        if not tokens: continue
        if len(tokens) == 1:
            result.append({"name": tokens[0].lstrip("*&"), "type": None, "default": default})
        else:
            result.append({
                "name":    tokens[-1].lstrip("*&"),
                "type":    " ".join(tokens[:-1]) or None,
                "default": default,
            })
    return result

def _cpp_param_parser(sig: str) -> List[dict]:
    """
    C++ specific: handles std::vector<T>&, const T&, pointers etc.
    Rejoins tokens split across :: by ctags signature field.
    """
    result = []
    for raw in _split_on_commas(sig):
        raw = raw.strip()
        if not raw:
            continue
        default: Optional[str] = None
        if "=" in raw:
            head, _, tail = raw.partition("=")
            raw, default = head.strip(), tail.strip()

        tokens = raw.split()
        if not tokens:
            continue

        # Last token is name — strip pointer/ref decorators
        name = tokens[-1].lstrip("*&")
        if len(tokens) == 1:
            result.append({"name": name, "type": None, "default": default})
        else:
            ptype = " ".join(tokens[:-1]).strip()
            # Rejoin broken std:: prefixes e.g. "std" ":vector<Book>" → "std::vector<Book>"
            ptype = re.sub(r"std\s*:\s*:", "std::", ptype)
            ptype = re.sub(r"\s*&\s*$", "&", ptype).strip()
            result.append({"name": name, "type": ptype or None, "default": default})
    return result

def _python_param_parser(sig: str) -> List[dict]:
    result = []
    for raw in _split_on_commas(sig):
        raw = raw.strip()
        if raw in ("/", "*", ""): continue
        default: Optional[str] = None
        if "=" in raw:
            depth = 0
            eq_pos = None
            for i, ch in enumerate(raw):
                if ch in "([{<":    depth += 1
                elif ch in ")]}>":  depth -= 1
                elif ch == "=" and depth == 0:
                    eq_pos = i; break
            if eq_pos is not None:
                default = raw[eq_pos + 1:].strip()
                raw     = raw[:eq_pos].strip()
        if ":" in raw:
            name_part, _, type_part = raw.partition(":")
            name  = name_part.strip().lstrip("*")
            ptype = type_part.strip() or None
        else:
            name, ptype = raw.lstrip("*"), None
        if name:
            result.append({"name": name, "type": ptype, "default": default})
    return result


_SIGNATURE_PARSERS: Dict[str, Callable[[str], List[dict]]] = {
    "python": _python_param_parser,
    "c++":    _cpp_param_parser,     # ← add
    "cpp":    _cpp_param_parser,     # ← add
    "c":      _cpp_param_parser,     # ← add
}

def _parse_parameters(sig: str, language: str) -> List[dict]:
    if not sig: return []
    parser = _SIGNATURE_PARSERS.get(language.lower(), _generic_param_parser)
    try:    return parser(sig)
    except: return _generic_param_parser(sig)


# ============================================================================
# 4.  Symbol ID + hash
# ============================================================================

def _build_symbol_id(
    source_root: Optional[Path],
    file_path: str,
    name: str,
) -> str:
    try:
        abs_file = Path(file_path).resolve()
        abs_root = source_root.resolve() if source_root else None
        if abs_root:
            try:
                # Use relative path of the FILE (not parent) as prefix
                rel_file = str(abs_file.relative_to(abs_root)).replace("\\", "/")
            except ValueError:
                rel_file = abs_file.name
        else:
            rel_file = str(abs_file).replace("\\", "/")
        # return f"{rel_file}::{name}"
        return f"{rel_file}_{name}"
    except Exception:
        return f"::{name}"


def _stable_hash(symbol_id: str) -> str:
    return hashlib.md5(symbol_id.encode()).hexdigest()[:16]


# ============================================================================
# 5.  Tag → symbol dict
#     NEW: extracts `language`, `access`, and `inherits` from ctags fields
# ============================================================================

def _tag_to_symbol(
    tag: dict,
    source_root: Optional[Path],
    fallback_language: str,
) -> Optional[dict]:
    kind_raw = (tag.get("kind") or tag.get("K") or "").lower().strip()
    if not kind_raw or kind_raw in _SKIP_KINDS:
        return None

    symbol_type = _KIND_MAP.get(kind_raw, "variable")
    file_path   = tag.get("path", "").strip()
    name        = tag.get("name", "").strip()
    if not file_path or not name:
        return None

    line_start = int(tag.get("line") or 0)
    line_end   = int(tag.get("end")  or 0)
    scope      = (tag.get("scope")     or "").strip()
    signature  = (tag.get("signature") or tag.get("S") or "").strip()
    typeref    = (tag.get("typeref")   or tag.get("t") or "").strip()

    # NEW: language emitted by ctags when --fields includes 'l'
    language = (tag.get("language") or fallback_language or "unknown").strip()

    # NEW: access modifier (public / private / protected)
    access = (tag.get("access") or tag.get("a") or "").strip() or None

    # NEW: base classes / interfaces (comma-separated string from ctags)
    inherits_raw = (tag.get("inherits") or tag.get("i") or "").strip()
    inherits: List[str] = (
        [b.strip() for b in inherits_raw.split(",") if b.strip()]
        if inherits_raw else []
    )

    return_type: Optional[str] = None
    if typeref:
        return_type = typeref.split(":")[-1].strip() or None

    parent_symbol: Optional[str] = None
    if scope:
        scope_name = re.split(r"[.:]", scope)[-1].strip()
        if scope_name:
            parent_symbol = _build_symbol_id(source_root, file_path, scope_name)

    symbol_id   = _build_symbol_id(source_root, file_path, name)
    symbol_hash = _stable_hash(symbol_id)

    return {
        "symbol_id":     symbol_id,
        "symbol_type":   symbol_type,
        "name":          name,
        "language":      language,           # NEW
        "access":        access,             # NEW
        "inherits":      inherits,           # NEW
        "parent_symbol": parent_symbol,
        "file_path":     file_path,
        "parameters":    _parse_parameters(signature, language),
        "return_type":   return_type,
        "calls":         [],   # filled by _build_calls_from_ctags
        "dependencies":  [],   # filled by _build_calls_from_ctags
        "line_range":    {
            "start": line_start,
            "end":   line_end if line_end >= line_start else line_start,
        },
        "ast_node_type": kind_raw,
        "symbol_hash":   symbol_hash,
        "role":          "",   # semantic-IR step
        "summary":       "",   # semantic-IR step
        "complexity":    0.0,  # compute_ast_complexity step
    }


# ============================================================================
# 6.  End-line patching  (unchanged)
# ============================================================================

def _patch_end_lines(symbols: List[dict]) -> None:
    by_file: Dict[str, List[dict]] = defaultdict(list)
    for s in symbols:
        by_file[s["file_path"]].append(s)

    for file_path, syms in by_file.items():
        syms.sort(key=lambda s: s["line_range"]["start"])
        total = 0
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                total = sum(1 for _ in fh)
        except Exception:
            pass
        for i, sym in enumerate(syms):
            lr = sym["line_range"]
            if lr["end"] > lr["start"]: continue
            start = lr["start"]
            end   = syms[i + 1]["line_range"]["start"] - 1 if i + 1 < len(syms) else total
            sym["line_range"]["end"] = max(start, end)


# ============================================================================
# 7.  Import tag → dependency dict  (replaces _ref_tag_to_dep)
# ============================================================================

def _import_tag_to_dep(
    tag: dict,
    source_root: Optional[Path],
) -> Optional[dict]:
    """
    Convert a ctags import tag (roles: imported/included/…) into a
    file-level dependency dict.
    """
    name      = (tag.get("name")  or "").strip()
    file_path = (tag.get("path")  or "").strip()
    if not name or not file_path:
        return None

    dep_type = "third_party"
    if name.startswith((".", "/", "\\")):
        dep_type = "local"
    elif source_root:
        try:
            candidate = (Path(file_path).parent / name).resolve()
            if candidate.exists():
                dep_type = "local"
            else:
                for ext in (
                    ".py", ".js", ".ts", ".java", ".go",
                    ".rs", ".cpp", ".c", ".cs", ".rb", ".kt",
                ):
                    if candidate.with_suffix(ext).exists():
                        dep_type = "local"
                        break
        except Exception:
            pass

    return {
        "name":      name,
        "type":      dep_type,
        "alias":     tag.get("alias") or None,
    }


# ============================================================================
# 8.  Call graph + inheritance from ctags
#     Replaces _merge_scip entirely — no SCIP required
# ============================================================================

def _build_calls_from_ctags(
    symbols:   List[dict],
    call_tags: List[dict],
    source_root: Optional[Path],
) -> Tuple[List[dict], List[dict]]:
    """
    Build call graph from ctags call_tags (roles: called/used).

    For each call tag:
      - tag["scope"]  = the caller symbol name
      - tag["name"]   = the callee symbol name

    Injects calls[] into each symbol dict and returns symbol_dependencies.
    """
    # name → list of symbols (multiple files may define same name)
    name_to_syms: Dict[str, List[dict]] = defaultdict(list)
    for sym in symbols:
        name_to_syms[sym["name"]].append(sym)

    defined_names = set(name_to_syms.keys())
    symbol_dependencies: List[dict] = []
    seen: set = set()

    for tag in call_tags:
        callee_name = (tag.get("name")  or "").strip()
        caller_raw  = (tag.get("scope") or "").strip()

        if not caller_raw or not callee_name:
            continue

        # scope can be "ClassName.method" or "ClassName::method" — take last segment
        caller_name = re.split(r"[.:]", caller_raw)[-1].strip()
        if not caller_name:
            continue

        for caller_sym in name_to_syms.get(caller_name, []):
            # Inject into calls[]
            existing_callees = {c["name"] for c in caller_sym["calls"]}
            if callee_name not in existing_callees:
                caller_sym["calls"].append({
                    "name":     callee_name,
                    "resolved": callee_name in defined_names,
                })

            # Build symbol_dependencies (only when callee is defined in project)
            for callee_sym in name_to_syms.get(callee_name, []):
                key = (caller_sym["symbol_id"], callee_sym["symbol_id"])
                if key not in seen:
                    seen.add(key)
                    symbol_dependencies.append({
                        "source": caller_sym["symbol_id"],
                        "target": callee_sym["symbol_id"],
                        "kind":   "call",
                    })

    # Deduplicate (seen set already handles this, but guard against edge cases)
    return symbols, symbol_dependencies

def _enrich_calls_for_files(
    symbols: List[dict],
    language_set: set,
    extractor_fn: Callable,
    pass_defined_names: bool = True,
) -> None:
    """
    Generic driver: collects files matching language_set,
    builds all_defined_names once, then calls extractor_fn per file.
    If pass_defined_names is False, calls extractor_fn(file_path, symbols) only.
    """
    all_defined_names = {s["name"] for s in symbols}
    target_files = {
        s["file_path"] for s in symbols
        if s.get("language", "").lower() in language_set
    }
    for file_path in target_files:
        if pass_defined_names:
            extractor_fn(file_path, symbols, all_defined_names)
        else:
            extractor_fn(file_path, symbols)

def _extract_python_calls(
    file_path: str,
    symbols: List[dict],
    all_defined_names: set,
) -> None:
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        tree   = _ast.parse(source)
    except Exception:
        return

    file_syms = {
        s["name"]: s for s in symbols
        if s["file_path"] == file_path
    }

    class CallVisitor(_ast.NodeVisitor):
        def __init__(self):
            self.current_func = None

        def visit_FunctionDef(self, node):
            prev = self.current_func
            self.current_func = node.name
            self.generic_visit(node)
            self.current_func = prev

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            if not self.current_func:
                self.generic_visit(node)
                return
            callee = None
            if isinstance(node.func, _ast.Name):
                callee = node.func.id
            elif isinstance(node.func, _ast.Attribute):
                callee = node.func.attr
            if callee and self.current_func in file_syms:
                caller_sym = file_syms[self.current_func]
                existing   = {c["name"] for c in caller_sym["calls"]}
                if callee not in existing:
                    caller_sym["calls"].append({
                        "name":     callee,
                        "resolved": callee in all_defined_names,  # ← cross-file
                    })
            self.generic_visit(node)

    CallVisitor().visit(tree)


def _enrich_python_calls(
    symbols: List[dict],
    source_root: Optional[Path],
) -> None:
    all_defined_names = {s["name"] for s in symbols}  # ← built once, all files

    python_files = {
        s["file_path"] for s in symbols
        if s.get("language", "").lower() in {"python", "py"}
    }
    for file_path in python_files:
        _extract_python_calls(file_path, symbols, all_defined_names)

# Matches: someMethod(  or  SomeClass.method(  or  this.method(
_JAVA_CALL_RE = re.compile(
    r'(?<!["\'/])'               # not inside string/comment
    r'\b([a-zA-Z_][a-zA-Z0-9_]*)' # method/function name
    r'\s*\(',                    # opening paren
)

_JAVA_NOISE = {
    # keywords that look like calls
    "if", "for", "while", "switch", "catch", "return",
    "new", "super", "this", "instanceof", "assert",
    "synchronized", "throw", "throws",
}

def _extract_java_calls(
    file_path: str,
    symbols: List[dict],
    all_defined_names: set,
) -> None:
    try:
        lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return

    file_syms = {
        s["name"]: s for s in symbols
        if s["file_path"] == file_path
        and s["symbol_type"] in {"function", "method"}
    }

    def _sym_at_line(lineno: int):
        for sym in file_syms.values():
            lr = sym["line_range"]
            if lr["start"] <= lineno <= lr["end"]:
                return sym
        return None

    in_block_comment = False
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if "/*" in stripped:  in_block_comment = True
        if "*/" in stripped:  in_block_comment = False; continue
        if in_block_comment:  continue
        if stripped.startswith("//"): continue

        caller_sym = _sym_at_line(lineno)
        if not caller_sym:
            continue

        for m in _JAVA_CALL_RE.finditer(line):
            callee = m.group(1)
            if callee in _JAVA_NOISE:
                continue
            existing = {c["name"] for c in caller_sym["calls"]}
            if callee not in existing:
                caller_sym["calls"].append({
                    "name":     callee,
                    "resolved": callee in all_defined_names,  # ← cross-file
                })


def _enrich_java_calls(symbols: List[dict]) -> None:
    _enrich_calls_for_files(symbols, {"java", "kotlin"}, _extract_java_calls)

_JS_CALL_RE = re.compile(
    r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\('
)
_JS_REF_RE = re.compile(r'(?<![.\w])([A-Za-z_$][A-Za-z0-9_$]*)\s*[,;)\]]')
_JS_NOISE = {
    "if", "for", "while", "switch", "catch", "function",
    "return", "typeof", "instanceof", "import", "require",
    "describe", "it", "test", "expect",   # test framework noise
}

def _extract_js_calls(
    file_path: str,
    symbols: List[dict],
    all_defined_names: set,
) -> None:
    try:
        lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return

    file_syms = {
        s["name"]: s for s in symbols
        if s["file_path"] == file_path
        and s["symbol_type"] in {"function", "method"}
    }

    def _sym_at_line(lineno: int):
        for sym in file_syms.values():
            lr = sym["line_range"]
            if lr["start"] <= lineno <= lr["end"]:
                return sym
        return None

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        line_clean = re.sub(r'//.*$', '', line)
        line_clean = re.sub(r'(["\`\']).*?\1', '""', line_clean)

        caller_sym = _sym_at_line(lineno)
        if not caller_sym:
            continue

        for m in _JS_CALL_RE.finditer(line_clean):
            callee = m.group(1)
            if callee in _JS_NOISE:
                continue
            existing = {c["name"] for c in caller_sym["calls"]}
            if callee not in existing:
                caller_sym["calls"].append({
                    "name":     callee,
                    "resolved": callee in all_defined_names,  # ← cross-file
                })


def _enrich_js_calls(symbols: List[dict]) -> None:
    _enrich_calls_for_files(
        symbols,
        {"javascript", "typescript", "js", "ts", "jsx", "tsx"},
        _extract_js_calls,
    )

_GO_CALL_RE = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')
_GO_REF_RE = re.compile(r':=\s*([A-Za-z_][A-Za-z0-9_]*)\b(?!\s*\()') 
_GO_NOISE = {
    "if", "for", "switch", "select", "go", "defer",
    "return", "make", "new", "len", "cap", "append",
    "copy", "delete", "close", "panic", "recover",
    "print", "println",
}

def _extract_go_calls(
    file_path: str,
    symbols: List[dict],
    all_defined_names: set,
) -> None:
    try:
        lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return

    file_syms = {
        s["name"]: s for s in symbols
        if s["file_path"] == file_path
        and s["symbol_type"] in {"function", "method"}
    }

    def _sym_at_line(lineno: int):
        for sym in file_syms.values():
            lr = sym["line_range"]
            if lr["start"] <= lineno <= lr["end"]:
                return sym
        return None

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        line_clean = re.sub(r'//.*$', '', line)
        line_clean = re.sub(r'".*?"', '""', line_clean)

        caller_sym = _sym_at_line(lineno)
        if not caller_sym:
            continue

        for m in _GO_CALL_RE.finditer(line_clean):
            callee = m.group(1)
            if callee in _GO_NOISE:
                continue
            existing = {c["name"] for c in caller_sym["calls"]}
            if callee not in existing:
                caller_sym["calls"].append({
                    "name":     callee,
                    "resolved": callee in all_defined_names,  # ← cross-file
                })


def _enrich_go_calls(symbols: List[dict]) -> None:
    _enrich_calls_for_files(symbols, {"go"}, _extract_go_calls)

_PERL_FUNC_RE   = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)?)\s*\(')
_PERL_METHOD_RE = re.compile(r'->([A-Za-z_][A-Za-z0-9_]+)\s*\(')
_PERL_REF_RE = re.compile(r'\\&([A-Za-z_][A-Za-z0-9_]*)')
_PERL_NOISE = {
    "if", "elsif", "unless", "while", "until", "for",
    "foreach", "sub", "return", "my", "our", "local",
    "use", "require", "print", "push", "pop", "shift",
    "unshift", "defined", "undef", "ref", "scalar",
    "chomp", "chop", "die", "warn", "eval", "sort",
    "map", "grep", "keys", "values", "each", "splice",
    "exists", "delete", "bless", "new",
}
_PERL_EXPORT_RE = re.compile(
    r'(?:our\s+)?@EXPORT(?:_OK)?\s*=\s*qw\(([^)]+)\)'
)

def _extract_perl_calls(
    file_path: str,
    symbols: List[dict],
    all_defined_names: set,
) -> None:
    try:
        lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return

    file_syms = {
        s["name"]: s for s in symbols
        if s["file_path"] == file_path
        and s["symbol_type"] in {"function", "method"}
    }

    def _sym_at_line(lineno: int):
        best = None
        best_size = float("inf")
        for sym in file_syms.values():
            lr = sym["line_range"]
            if lr["start"] <= lineno <= lr["end"]:
                size = lr["end"] - lr["start"]
                if size < best_size:
                    best_size = size
                    best = sym
        return best

    def _add_call(caller_sym: dict, callee: str) -> None:
        if not callee:
            return
        callee_short = callee.split("::")[-1]
        if callee_short in _PERL_NOISE or len(callee_short) <= 1:
            return
        existing = {c["name"] for c in caller_sym["calls"]}
        if callee_short not in existing:
            caller_sym["calls"].append({
                "name":     callee_short,
                "resolved": callee_short in all_defined_names,
            })

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        line_clean = re.sub(r"#.*$",        "",   line)
        line_clean = re.sub(r'(["\']).*?\1', '""', line_clean)

        caller_sym = _sym_at_line(lineno)
        if not caller_sym:
            continue

        for m in _PERL_FUNC_RE.finditer(line_clean):
            _add_call(caller_sym, m.group(1))

        for m in _PERL_METHOD_RE.finditer(line_clean):
            _add_call(caller_sym, m.group(1))

        for m in _PERL_REF_RE.finditer(line_clean):
            _add_call(caller_sym, m.group(1))


def _enrich_perl_calls(symbols: List[dict]) -> None:
    _enrich_calls_for_files(symbols, {"perl"}, _extract_perl_calls)

_PERL_USE_RE = re.compile(
    r'^\s*(?:use|require)\s+([A-Za-z][A-Za-z0-9:]+)'
)

_PERL_CORE_MODULES = {
    "strict", "warnings", "Exporter", "POSIX", "Carp",
    "Data::Dumper", "Scalar::Util", "List::Util",
    "File::Basename", "File::Path", "Cwd", "MIME::Base64",
    "Encode", "utf8", "constant", "base", "parent",
    "overload", "vars", "lib",
}

def _extract_perl_imports(
    file_path: str,
    source_root: Optional[Path],
) -> List[dict]:
    deps = []
    try:
        lines = Path(file_path).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except Exception:
        return deps

    for line in lines:
        m = _PERL_USE_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        if name in _PERL_CORE_MODULES:
            continue

        # Resolve local vs third_party
        dep_type = "third_party"
        if source_root:
            # BookUtils → BookUtils.pm,  Foo::Bar → Foo/Bar.pm
            candidate = source_root / (name.replace("::", "/") + ".pm")
            if candidate.exists():
                dep_type = "local"

        deps.append({
            "name":      name,
            "type":      dep_type,
            "alias":     None,
        })
    return deps

_PERL_PARAM_RE = re.compile(r'my\s*\(([^)]+)\)\s*=\s*@_')

def _extract_perl_params(file_path: str, symbols: List[dict]) -> None:
    try:
        lines = Path(file_path).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except Exception:
        return

    file_syms = [
        s for s in symbols
        if s["file_path"] == file_path
        and s["symbol_type"] in {"function", "method"}
    ]

    for sym in file_syms:
        start = sym["line_range"]["start"]
        end   = sym["line_range"]["end"]
        # Search first 5 lines of function body for param declaration
        for line in lines[start: min(start + 5, end)]:
            m = _PERL_PARAM_RE.search(line)
            if not m:
                continue
            raw_params = m.group(1)
            params = []
            for p in raw_params.split(","):
                p = p.strip().lstrip("$@%&\\").strip()
                if p:
                    params.append({
                        "name":    p,
                        "type":    None,
                        "default": None,
                    })
            sym["parameters"] = params
            break  # only first @_ assignment counts


def _enrich_perl_params(symbols: List[dict]) -> None:
    _enrich_calls_for_files(symbols, {"perl"}, _extract_perl_params, pass_defined_names=False)


def _extract_perl_exports(
    file_path: str,
    symbols: List[dict],
) -> None:
    """
    Mark symbols that are explicitly exported via @EXPORT or @EXPORT_OK
    by setting access='public'. Non-exported symbols get access='private'.
    Helps migration tools identify the module's public API.
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return

    exported_names: set = set()
    for m in _PERL_EXPORT_RE.finditer(source):
        for name in m.group(1).split():
            exported_names.add(name.strip())

    if not exported_names:
        return

    for sym in symbols:
        if sym["file_path"] != file_path:
            continue
        if sym["symbol_type"] not in {"function", "method"}:
            continue
        # Mark access based on export list
        sym["access"] = "public" if sym["name"] in exported_names else "private"


def _enrich_perl_exports(symbols: List[dict]) -> None:
    _enrich_calls_for_files(symbols, {"perl"}, _extract_perl_exports, pass_defined_names=False)

# ── JS/TS export detection ─────────────────────────────────────────────────

_JS_EXPORT_DECL_RE = re.compile(
    r'^\s*export\s+(?:default\s+)?'
    r'(?:(?:async\s+)?function\*?\s+|class\s+|const\s+|let\s+|var\s+)?'
    r'([A-Za-z_$][A-Za-z0-9_$]*)'
)
_JS_EXPORT_LIST_RE = re.compile(r'\bexport\s*\{([^}]+)\}')


def _enrich_js_exports(symbols: List[dict]) -> None:
    """
    Detect export status for JS/TS symbols ctags did not mark.
    Sets access='public' for exported names, 'private' for non-exported.
    Handles: export const/function/class, export default, export { a, b as c }.
    Only fills where ctags did not already emit an access modifier.
    """
    js_langs = {"javascript", "typescript", "js", "ts", "jsx", "tsx"}
    files = {
        s["file_path"] for s in symbols
        if s.get("language", "").lower() in js_langs
    }
    for file_path in files:
        try:
            source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        exported: set = set()

        for line in source.splitlines():
            m = _JS_EXPORT_DECL_RE.match(line)
            if m:
                exported.add(m.group(1))

        for m in _JS_EXPORT_LIST_RE.finditer(source):
            for entry in m.group(1).split(","):
                name = entry.strip().split(" as ")[0].strip()
                if name:
                    exported.add(name)

        for sym in symbols:
            if sym["file_path"] != file_path:
                continue
            if sym.get("access"):
                continue
            sym["access"] = "public" if sym.get("name") in exported else "private"


# ── Python access via underscore convention ────────────────────────────────

def _enrich_python_access(symbols: List[dict]) -> None:
    """
    Fill access field using Python's underscore naming convention.
    Only applied where ctags did not already emit an access modifier.
      __name  (non-dunder) → private (name-mangled)
      _name                → protected
      name                 → public
    Dunder methods (__init__, __str__, etc.) are left untouched;
    they are not access-restricted in any meaningful sense.
    """
    for sym in symbols:
        if sym.get("language", "").lower() not in {"python", "py"}:
            continue
        if sym.get("access"):
            continue
        name = sym.get("name", "")
        if not name:
            continue
        if name.startswith("__") and not name.endswith("__"):
            sym["access"] = "private"
        elif name.startswith("_"):
            sym["access"] = "protected"
        else:
            sym["access"] = "public"


# ── Go access via capitalisation rule ─────────────────────────────────────

def _enrich_go_access(symbols: List[dict]) -> None:
    """
    Fill access field using Go's capitalisation rule:
    uppercase first letter → exported (public), lowercase → unexported (private).
    Only applied where ctags did not already emit an access modifier.
    """
    for sym in symbols:
        if sym.get("language", "").lower() != "go":
            continue
        if sym.get("access"):
            continue
        name = sym.get("name", "")
        if not name:
            continue
        sym["access"] = "public" if name[0].isupper() else "private"

# Registry — add new language call enrichers here without touching call sites
_CALL_ENRICHERS: Dict[str, Callable] = {
    "python":     _enrich_python_calls,
    "java":       _enrich_java_calls,
    "kotlin":     _enrich_java_calls,
    "javascript": _enrich_js_calls,
    "typescript": _enrich_js_calls,
    "go":         _enrich_go_calls,
    "perl":       _enrich_perl_calls,
}

# Registry — add new language symbol enrichers (params, exports, access, etc.)
# Parallel to _CALL_ENRICHERS; covers symbol-level annotation ctags doesn't emit.
_SYMBOL_ENRICHERS: Dict[str, List[Callable]] = {
    "perl":       [_enrich_perl_params, _enrich_perl_exports],
    "python":     [_enrich_python_access],
    "go":         [_enrich_go_access],
    "javascript": [_enrich_js_exports],
    "typescript": [_enrich_js_exports],
    "js":         [_enrich_js_exports],
    "ts":         [_enrich_js_exports],
    "jsx":        [_enrich_js_exports],
    "tsx":        [_enrich_js_exports],
}


def _enrich_symbols_by_language(symbols: List[dict]) -> None:
    """
    Dispatch symbol-level enrichment (params, exports, access, etc.) per language.
    Language-agnostic — behaviour entirely determined by _SYMBOL_ENRICHERS.
    """
    languages_present = {s.get("language", "").lower() for s in symbols}
    for lang in languages_present:
        for enricher in _SYMBOL_ENRICHERS.get(lang, []):
            try:
                enricher(symbols)
            except Exception as e:
                logger.warning(f"Symbol enricher failed for {lang}: {e}")

# ── File dependency enrichment registry ────────────────────────────────────
# For languages where ctags import tags are incomplete or missing.
# Each enricher signature: (file_path: str, source_root: Optional[Path]) -> List[dict]

# ── Python import extraction (AST-based) ──────────────────────────────────

def _extract_python_imports(
    file_path:   str,
    source_root: Optional[Path],
) -> List[dict]:
    """
    Extract Python imports via AST — more complete than ctags for:
      - relative imports  (from . import x, from ..pkg import y)
      - conditional imports inside if/try blocks
      - star imports      (from module import *)
    Only fills entries not already emitted by ctags import tags.
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        tree   = _ast.parse(source)
    except Exception:
        return []

    deps: List[dict] = []
    seen: set        = set()

    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for alias in node.names:
                name = alias.name
                if name and name not in seen:
                    seen.add(name)
                    deps.append({
                        "name":  name,
                        "type":  "third_party",
                        "alias": alias.asname or None,
                    })

        elif isinstance(node, _ast.ImportFrom):
            module   = node.module or ""
            level    = node.level          # number of leading dots
            if level > 0:
                name     = ("." * level) + module
                dep_type = "local"
            else:
                name     = module
                dep_type = "third_party"
            if name and name not in seen:
                seen.add(name)
                deps.append({
                    "name":  name,
                    "type":  dep_type,
                    "alias": None,
                })

    # Resolve absolute imports to local when the module file exists
    if source_root:
        for dep in deps:
            if dep["type"] != "third_party":
                continue
            clean        = dep["name"].lstrip(".")
            module_file  = source_root / (clean.replace(".", "/") + ".py")
            package_dir  = source_root / clean.replace(".", "/")
            if module_file.exists() or package_dir.is_dir():
                dep["type"] = "local"

    return deps


# ── JS/TS import extraction (regex-based) ─────────────────────────────────
# Covers gaps ctags leaves: CommonJS require(), dynamic import(),
# and re-export patterns.

_JS_IMPORT_FROM_RE   = re.compile(
    r'^\s*(?:import|export)\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
    re.MULTILINE,
)
_JS_IMPORT_BARE_RE   = re.compile(
    r'^\s*import\s+[\'"]([^\'"]+)[\'"]',
    re.MULTILINE,
)
_JS_REQUIRE_RE       = re.compile(
    r'(?:require|import)\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
)


def _extract_js_imports(
    file_path:   str,
    source_root: Optional[Path],
) -> List[dict]:
    """
    Extract JS/TS imports — covers:
      - ES6  import X from 'y' / export X from 'y'
      - bare import 'side-effect-module'
      - CommonJS  require('x')
      - dynamic   import('x')
    Only fills entries not already emitted by ctags import tags.
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    deps: List[dict] = []
    seen: set        = set()

    def _add(name: str) -> None:
        if not name or name in seen:
            return
        seen.add(name)
        dep_type = "local" if name.startswith((".", "/")) else "third_party"
        # Attempt local resolution for relative-looking paths
        if dep_type == "third_party" and source_root:
            base = Path(file_path).parent / name
            for ext in (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"):
                if base.with_suffix(ext).exists():
                    dep_type = "local"
                    break
            else:
                if (base / "index.js").exists() or (base / "index.ts").exists():
                    dep_type = "local"
        deps.append({"name": name, "type": dep_type, "alias": None})

    for m in _JS_IMPORT_FROM_RE.finditer(source):
        _add(m.group(1))
    for m in _JS_IMPORT_BARE_RE.finditer(source):
        _add(m.group(1))
    for m in _JS_REQUIRE_RE.finditer(source):
        _add(m.group(1))

    return deps

_FILE_DEP_ENRICHERS: Dict[str, Callable] = {
    "perl":       _extract_perl_imports,
    "python":     _extract_python_imports,
    "javascript": _extract_js_imports,
    "typescript": _extract_js_imports,
    "js":         _extract_js_imports,
    "ts":         _extract_js_imports,
    "jsx":        _extract_js_imports,
    "tsx":        _extract_js_imports,
}


def _enrich_file_deps_by_language(
    file_paths:  List[str],
    language:    str,
    source_root: Optional[Path],
) -> List[dict]:
    """
    Extract file-level dependencies for languages where ctags misses imports.
    Returns flat list of {source, target, type, alias} dicts.
    Language-agnostic — behaviour entirely determined by _FILE_DEP_ENRICHERS.
    """
    enricher = _FILE_DEP_ENRICHERS.get(language.lower())
    if not enricher:
        return []

    file_dependencies: List[dict] = []
    for file_path in file_paths:
        try:
            for dep in enricher(file_path, source_root):
                file_dependencies.append({
                    "source": file_path,
                    "target": dep["name"],
                    "type":   dep["type"],
                    "alias":  dep["alias"],
                })
        except Exception as e:
            logger.warning(f"File dep enricher failed for {file_path}: {e}")
    return file_dependencies


# ── Perl test framework detection ──────────────────────────────────────────

_FRAMEWORK_PATTERNS: List[dict] = [
    {
        "name": "test_class",
        "detect": lambda src: "Test::Class" in src or "Test::Unit" in src,
        "regex": re.compile(
            r'^sub\s+([a-zA-Z_]\w*)\s*(?::\s*Test[^{]*)?\{',
            re.MULTILINE,
        ),
        "groups": [0],
        "noise": {"BEGIN", "END", "AUTOLOAD", "DESTROY", "import", "new",
                  "init", "setup", "teardown", "set_up", "tear_down"},
    },
    {
        "name": "test_spec",
        "detect": lambda src: bool(re.search(r'\bdescribe\s+[\'"]', src)) or "Test::Spec" in src,
        "regex": re.compile(r'\b(?:describe|context|it)\s+[\'"]([^\'"]+)[\'"]'),
        "groups": [0],
        "noise": set(),
    },
    {
        "name": "test_bdd",
        "detect": lambda src: "Test::BDD::Cucumber" in src or bool(re.search(r'\b(Given|When|Then)\s+[\'"]', src)),
        "regex": re.compile(r'\b(?:Given|When|Then|And|But|Step)\s+[\'"]([^\'"]+)[\'"]'),
        "groups": [0],
        "noise": set(),
    },
    {
        "name": "test_unit",
        "detect": lambda src: bool(re.search(r'\bsub\s+test_[a-zA-Z_]+\s*\{', src)),
        "regex": re.compile(r'^sub\s+(test_[a-zA-Z_]\w*)\s*\{', re.MULTILINE),
        "groups": [0],
        "noise": set(),
    },
    {
        "name": "test2",
        "detect": lambda src: "Test2::V0" in src or "Test2::Tools" in src,
        "regex": re.compile(
            r'\bsubtest\s+[\'"]([^\'"]+)[\'"]'
            r'|^sub\s+([a-zA-Z_]\w*)\s*\{'
            r'|^my\s+\$([a-zA-Z_]\w*)\s*=\s*sub\s*\{',
            re.MULTILINE,
        ),
        "groups": [0, 1, 2],
        "noise": {"BEGIN", "END", "AUTOLOAD", "DESTROY", "import", "new",
                  "init", "setup", "teardown"},
    },
    {
        "name": "test_more",  # broadest fallback — keep last
        "detect": lambda src: (
            "Test::More" in src or "done_testing" in src or "plan tests" in src
        ),
        "regex": re.compile(
            r'\bsubtest\s+[\'"]([^\'"]+)[\'"]'
            r'|^sub\s+([a-zA-Z_]\w*)\s*\{'
            r'|^my\s+\$([a-zA-Z_]\w*)\s*=\s*sub\s*\{',
            re.MULTILINE,
        ),
        "groups": [0, 1, 2],
        "noise": {"BEGIN", "END", "AUTOLOAD", "DESTROY", "import", "new",
                  "init", "setup", "teardown"},
    },
]


def _detect_perl_test_framework(source: str) -> dict:
    """
    Returns the first matching framework pattern dict.
    Falls back to test_more as the safest generic option.
    """
    for pattern in _FRAMEWORK_PATTERNS:
        if pattern["detect"](source):
            logger.debug(f"Detected Perl test framework: {pattern['name']}")
            return pattern
    return _FRAMEWORK_PATTERNS[-1]


def _enrich_calls_by_language(
    symbols:     List[dict],
    source_root: Optional[Path],
) -> None:
    """
    Dispatch call enrichment per language.
    Python is AST-based and takes source_root.
    All others are regex-based via _enrich_calls_for_files.
    """
    languages_present = {s.get("language", "").lower() for s in symbols}
    for lang in languages_present:
        enricher = _CALL_ENRICHERS.get(lang)
        if not enricher:
            continue
        try:
            if lang == "python":
                enricher(symbols, source_root)
            else:
                enricher(symbols)
        except Exception as e:
            logger.warning(f"Call enricher failed for {lang}: {e}")


def _build_inheritance_deps(
    symbols:         List[dict],
    definition_tags: List[dict],
    source_root:     Optional[Path],
) -> List[dict]:
    """
    Build inheritance/implementation edges from the `inherits` field
    that ctags emits when --fields includes 'i'.

    Works for: Python (class A(B)), Java (extends/implements),
    TypeScript (extends/implements), Ruby, Go (struct embedding),
    C++ (: public Base), C# (: IInterface), Rust (impl Trait for X), etc.

    Returns a list of symbol_dependency dicts with kind='inherits'.
    """
    name_to_sym: Dict[str, dict] = {}
    for sym in symbols:
        name_to_sym[sym["name"]] = sym

    deps: List[dict] = []
    seen: set = set()

    for tag in definition_tags:
        inherits_raw = (tag.get("inherits") or tag.get("i") or "").strip()
        if not inherits_raw:
            continue

        child_name = (tag.get("name") or "").strip()
        child_sym  = name_to_sym.get(child_name)
        if not child_sym:
            continue

        for parent_name in inherits_raw.split(","):
            parent_name = parent_name.strip()
            if not parent_name:
                continue
            parent_sym = name_to_sym.get(parent_name)
            if not parent_sym:
                continue
            key = (child_sym["symbol_id"], parent_sym["symbol_id"])
            if key not in seen:
                seen.add(key)
                deps.append({
                    "source": child_sym["symbol_id"],
                    "target": parent_sym["symbol_id"],
                    "kind":   "inherits",
                })

    return deps


# ============================================================================
# 9.  File index  (unchanged)
# ============================================================================

def _build_file_index(symbols: List[dict]) -> Dict[str, List[dict]]:
    index: Dict[str, List[dict]] = defaultdict(list)
    for sym in symbols:
        index[sym["file_path"]].append({
            "symbol_id":     sym["symbol_id"],
            "type":          sym["symbol_type"],
            "name":          sym["name"],
            "language":      sym.get("language", ""),   # NEW
            "access":        sym.get("access"),          # NEW
            "parent_symbol": sym["parent_symbol"],
        })
    return dict(index)