"""Deterministic local integration with Specfy Stack Analyser.

The analyzer is installed in the agent container at build time. We never call
npx against the network during a migration. If it is unavailable, callers can
fall back to the local Python scanner.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)
STACK_ANALYZER_VERSION = os.getenv("STACK_ANALYZER_VERSION", "1.27.6")

def run_stack_analyser(source_path: str, output_dir: str) -> dict:
    source = Path(source_path).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / "stack_analyser.json"
    output_file.unlink(missing_ok=True)

    executable = shutil.which("stack-analyser")
    if not executable:
        return {"success": False, "error": "stack-analyser executable not installed", "output_file": None}

    command = [executable, str(source), "--output=stack_analyser.json"]
    try:
        result = subprocess.run(
            command, cwd=str(out_dir), text=True, capture_output=True, timeout=180, check=False
        )
        if result.returncode != 0:
            return {
                "success": False, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr, "output_file": None,
            }
        if not output_file.exists():
            # Be tolerant of CLI versions that emit a default JSON filename.
            candidates = sorted(out_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                output_file = candidates[0]
            else:
                return {"success": False, "error": "Stack Analyser produced no JSON output", "output_file": None}
        return {
            "success": True, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
            "output_file": str(output_file),
        }
    except subprocess.TimeoutExpired as exc:
        return {"success": False, "error": "Stack Analyser timed out after 180 seconds", "stdout": exc.stdout or "", "stderr": exc.stderr or "", "output_file": None}
    except Exception as exc:
        return {"success": False, "error": str(exc), "output_file": None}


def parse_stack_analyzer(raw: Dict[str, Any]) -> Dict[str, Any]:
    languages = raw.get("languages") or {}
    languages_clean = [{"name": lang, "lines": count} for lang, count in languages.items()]
    dependencies_clean = []
    for dep in raw.get("dependencies") or []:
        if isinstance(dep, (list, tuple)) and len(dep) >= 2:
            dependencies_clean.append({"type": dep[0], "package": dep[1], "version": dep[2] if len(dep) > 2 else ""})
    children_clean = [{"name": c.get("name"), "tech": c.get("tech"), "path": c.get("path", [])} for c in (raw.get("childs") or []) if isinstance(c, dict)]
    return {
        "name": raw.get("name"),
        "technologies": raw.get("techs") or [],
        "languages": languages_clean,
        "dependencies": dependencies_clean,
        "children": children_clean,
    }


def analyze_stack(source_path: str, output_dir: str) -> Dict[str, Any]:
    result = run_stack_analyser(source_path, output_dir)
    if not result.get("success") or not result.get("output_file"):
        return {"success": False, "error": result.get("error") or result.get("stderr") or "Stack Analyser failed"}
    try:
        raw = json.loads(Path(result["output_file"]).read_text(encoding="utf-8"))
        parsed = parse_stack_analyzer(raw)
        parsed["success"] = True
        parsed["raw_output_file"] = result["output_file"]
        return parsed
    except Exception as exc:
        logger.warning("Could not parse Stack Analyser output: %s", exc)
        return {"success": False, "error": f"Invalid Stack Analyser JSON: {exc}"}


def save_parsed_json(parsed_data: Dict[str, Any], output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "stack_parsed.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parsed_data, f, indent=4)
    return output_path
