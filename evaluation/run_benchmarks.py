"""Run the repository's deterministic multi-language benchmark suite."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = ROOT / "benchmarks"


def run(command: str, cwd: Path, timeout: int = 120) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        p = subprocess.run(command, cwd=cwd, shell=True, text=True,
                           capture_output=True, timeout=timeout, check=False)
        return {
            "command": command,
            "passed": p.returncode == 0,
            "return_code": p.returncode,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "output_tail": (p.stdout + "\n" + p.stderr).strip()[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command, "passed": False, "return_code": None,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "output_tail": str(exc)[-3000:], "timed_out": True,
        }


def file_stats(path: Path) -> dict[str, int]:
    files = [p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts]
    return {"files": len(files), "lines": sum(len(p.read_text(encoding="utf-8", errors="ignore").splitlines()) for p in files)}


def main() -> int:
    cases = []
    for metadata in sorted(BENCHMARK_ROOT.glob("*/metadata.json")):
        data = json.loads(metadata.read_text(encoding="utf-8"))
        case_root = metadata.parent
        source = case_root / "source"
        target = case_root / "target"
        result: dict[str, Any] = {
            "name": data["name"],
            "source_language": data["source_language"],
            "target_language": data["target_language"],
            "transformation": data.get("transformation", "unspecified"),
            "source": file_stats(source),
            "target": file_stats(target),
            "validation": {},
        }
        if data.get("build_command"):
            result["validation"]["build"] = run(data["build_command"], target)
        if data.get("syntax_command"):
            result["validation"]["syntax"] = run(data["syntax_command"], target)
        if data.get("test_command"):
            result["validation"]["tests"] = run(data["test_command"], target)
        result["passed"] = all(item["passed"] for item in result["validation"].values())
        cases.append(result)

    report = {
        "suite": "ACMP portfolio validation suite",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cases": cases,
        "summary": {
            "total": len(cases),
            "passed": sum(c["passed"] for c in cases),
            "failed": sum(not c["passed"] for c in cases),
        },
        "scope_note": "Targets are hand-authored reference implementations used to validate the evaluation contract; results are not claimed as LLM semantic-equivalence accuracy.",
    }
    out = BENCHMARK_ROOT / "results.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
