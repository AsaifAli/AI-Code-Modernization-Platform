from __future__ import annotations
import os
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel
logger = logging.getLogger(__name__)
# ============================================================================
# File helpers
# ============================================================================

class FilePayload(BaseModel):
    name:    str   # relative path, e.g. "src/utils.py"
    content: str   # raw file text


class ParseRequest(BaseModel):
    files: List[FilePayload]


class ParseResponse(BaseModel):
    definition_tags: List[dict] = []
    import_tags:     List[dict] = []
    call_tags:       List[dict] = []
    errors:          List[str]  = []

# ============================================================================
# Ctags binary discovery
# ============================================================================

def _find_ctags() -> Optional[str]:
    """Resolve Universal Ctags from an optional override or the container PATH.

    CTAGS_BIN is intentionally an executable name/path, not a host-specific
    developer path.  Docker installs Universal Ctags into the image, so the
    normal production value is simply ``ctags`` (or no variable at all).
    """
    configured = os.environ.get("CTAGS_BIN", "").strip()
    candidates = [configured] if configured else []
    candidates.extend(["ctags", "universal-ctags"])

    seen = set()
    for name in candidates:
        if not name or name in seen:
            continue
        seen.add(name)
        path = shutil.which(name)
        if not path and os.path.isfile(name) and os.access(name, os.X_OK):
            path = name
        if not path:
            continue
        try:
            out = subprocess.check_output(
                [path, "--version"], stderr=subprocess.STDOUT,
                text=True, timeout=5,
            )
            if "universal ctags" in out.lower():
                logger.info("Universal Ctags resolved to %s", path)
                return path
            logger.warning("Ignoring non-Universal Ctags executable: %s", path)
        except Exception as exc:
            logger.warning("Unable to validate ctags executable %s: %s", path, exc)
    return None


CTAGS_BIN = _find_ctags()
  
def _write_files(tmpdir: Path, files: List[FilePayload]) -> None:
    """Write all files into tmpdir, preserving sub-directory structure."""
    for f in files:
        dest = tmpdir / f.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f.content, encoding="utf-8")


def _clean_path(tag: dict, tmpdir_resolved: Path) -> dict:
    """
    Strip tmpdir prefix from the ctags 'path' field → relative path.

    FIX: Uses resolved Path objects on BOTH sides so Windows long paths
    and mixed separators don't cause relative_to() to fail.
    """
    raw = tag.get("path", "")
    if not raw:
        return tag
    try:
        tag["path"] = (
            str(Path(raw).resolve().relative_to(tmpdir_resolved))
            .replace("\\", "/")
        )
    except Exception:
        # Fallback: normalise separators and return unchanged
        tag["path"] = raw.replace("\\", "/")
    return tag


# ============================================================================
# Tag classification
# ============================================================================

# ── Tag role buckets ──────────────────────────────────────────────────────────
# Priority when a tag has multiple roles: import > call > definition
# This matters for roles like "used" which ctags applies to both
# Perl `use` statements (import) and general references (call).

_IMPORT_ROLES = {
    "imported", "included", "required", "loaded",
    "extended", "implemented", "inherited",
    "system", "local",
    "used",   # ← Perl `use` statements; import priority over call
}

_CALL_ROLES = {
    "called",
}

_DEFINITION_ROLES = {
    "def", "definition", "defined",
}


def _classify_tag(tag: dict) -> str:
    """
    Returns 'definition' | 'call' | 'import'.

    Priority: import > call > definition.
    'import' takes priority over 'call' because some roles (e.g. 'used'
    in Perl) appear in both import and call contexts — the import
    interpretation is always more structurally useful for dependency graphs.

    Language-agnostic: classification is driven entirely by the
    _IMPORT_ROLES and _CALL_ROLES sets above. Add new language-specific
    role strings to those sets without touching this function.
    """
    roles  = str(tag.get("roles") or "").lower()
    extras = str(tag.get("extras") or "").lower()

    # No roles field or explicitly a definition
    if not roles or roles in _DEFINITION_ROLES:
        return "definition"

    # Import check first — takes priority over call
    if any(r in roles for r in _IMPORT_ROLES):
        return "import"

    # Call check second
    if any(r in roles for r in _CALL_ROLES):
        return "call"

    # Extras fallback — ctags sometimes puts "reference" here
    if "reference" in extras:
        return "import"

    # Unknown roles default to definition (safe fallback)
    return "definition"


# ============================================================================
# Core ctags runner
# ============================================================================

def _run_ctags(
    tmpdir_resolved: Path,
) -> Tuple[List[dict], List[dict], List[dict], List[str]]:
    """
    Run Universal Ctags on all files inside tmpdir_resolved.
    Returns (definition_tags, import_tags, call_tags, errors).

    FIX (Windows): 
      - tmpdir_resolved is already a resolved absolute Path
      - all file paths in the filelist are resolved absolute paths
      - filelist path itself is resolved before passing to --files-from
      - cwd is set to tmpdir so ctags can resolve relative refs internally
    """
    if not CTAGS_BIN:
        return [], [], [], ["Universal Ctags not found on server"]

    # Collect all files — resolve each to absolute path (critical on Windows)
    files = [
        str(p.resolve())
        for p in tmpdir_resolved.rglob("*")
        if p.is_file() and p.name != "_filelist.txt"
        and "__MACOSX" not in p.parts
        and not p.name.startswith("._")
    ]
    if not files:
        return [], [], [], []

    cmd = [
    CTAGS_BIN,
    "--output-format=json",
    "--fields=*",
    "--extras=+r",
    "--languages=all",
    "--langmap=Perl:+.t", 
    "--input-encoding=utf-8",
    "--output-encoding=utf-8",
    *files,
]
    logger.info(f"ctags files being passed: {files}")
    logger.info(f"ctags command: {' '.join(cmd)}")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            cwd=str(tmpdir_resolved),   # FIX: set cwd so ctags resolves paths correctly
        )
    except subprocess.TimeoutExpired:
        return [], [], [], ["ctags timed out after 60s"]
    except Exception as e:
        return [], [], [], [str(e)]

    errors: List[str] = []
    if proc.returncode not in (0, 1):
        errors.append(f"ctags exit {proc.returncode}: {proc.stderr[:300]}")

    defs:    List[dict] = []
    imports: List[dict] = []
    calls:   List[dict] = []

    for raw in proc.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            tag = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # Skip ctags pseudo-tags (metadata lines like !_TAG_...)
        if tag.get("_type") == "ptag":
            continue

        bucket = _classify_tag(tag)
        if bucket == "call":
            calls.append(tag)
        elif bucket == "import":
            imports.append(tag)
        else:
            defs.append(tag)

    logger.info(
        f"ctags: {len(defs)} defs, {len(imports)} imports, {len(calls)} calls"
    )
    # Temporary — add inside _run_ctags after parsing
    for tag in defs + imports + calls:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"TAG: {tag.get('name')} | kind={tag.get('kind')} | roles={tag.get('roles')}"
            )
    return defs, imports, calls, errors


def parse(request: ParseRequest) -> ParseResponse:
    if not CTAGS_BIN:
        logger.error("Universal Ctags not found. Set CTAGS_BIN env var or install ctags.")
        return ParseResponse(errors=["Universal Ctags not found on server"])

    if not request.files:
        logger.warning("parse() called with no files.")
        return ParseResponse(errors=["No files provided"])

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str).resolve()

        _write_files(tmpdir, request.files)
        defs, imports, calls, errors = _run_ctags(tmpdir)

        defs    = [_clean_path(t, tmpdir) for t in defs]
        imports = [_clean_path(t, tmpdir) for t in imports]
        calls   = [_clean_path(t, tmpdir) for t in calls]

    logger.info(
        f"parse: {len(defs)} defs, {len(imports)} imports, {len(calls)} calls"
    )
    return ParseResponse(
        definition_tags=defs,
        import_tags=imports,
        call_tags=calls,
        errors=errors,
    )
