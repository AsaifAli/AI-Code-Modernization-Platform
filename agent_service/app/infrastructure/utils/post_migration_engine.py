"""
Post-migration engineering gate.

This module turns a generated code tree into a release candidate by:
1. detecting the target ecosystem,
2. generating a stack-aware CI workflow,
3. running deterministic syntax/lint/test/build checks,
4. optionally asking an Agno repair agent to make minimal file edits,
5. repeating validation until the project passes or the repair budget is exhausted.

Execution is intentionally allow-listed: arbitrary shell commands are never accepted
from the model. The model can edit files through Agno FileTools, while this module
controls which validation commands may execute.
"""
from __future__ import annotations

import json
import logging
import re
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

from app.infrastructure.utils.language_adapters import get_adapter, detect_by_extension, adapters

logger = logging.getLogger(__name__)

IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "vendor", "target", "build", "dist",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next",
}

STACK_FILES = {adapter.key: adapter.manifest_files for adapter in adapters()}


@dataclass
class CheckResult:
    name: str
    command: list[str]
    status: str  # passed | failed | skipped | unavailable
    return_code: Optional[int]
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    required: bool = True
    category: str = "validation"

    @property
    def passed(self) -> bool:
        return self.status == "passed"

def _safe_text(value: str, limit: int = 12000) -> str:
    value = value or ""
    return value[-limit:]

def _find_files(root: Path, names: tuple[str, ...]) -> list[Path]:
    found = []
    for name in names:
        direct = root / name
        if direct.exists():
            found.append(direct)
        if not found:
            # A migration may put the application in backend/ or src/.
            for p in root.rglob(name):
                if any(part in IGNORED_DIRS for part in p.parts):
                    continue
                found.append(p)
                if len(found) >= 3:
                    break
    return found

def detect_target_stack(root: Path) -> dict[str, Any]:
    root = root.resolve()
    scores: dict[str, int] = {k: 0 for k in STACK_FILES}
    evidence: dict[str, list[str]] = {k: [] for k in STACK_FILES}

    for stack, names in STACK_FILES.items():
        for p in _find_files(root, names):
            scores[stack] += 2
            evidence[stack].append(str(p.relative_to(root)))

    # Stronger framework/package signals.
    package = root / "package.json"
    if package.exists():
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if any(k in deps for k in ("typescript", "ts-node", "@types/node")):
                evidence["node"].append("TypeScript dependency")
            if any(k in deps for k in ("react", "next", "vite", "vue", "angular")):
                evidence["node"].append("frontend framework dependency")
        except Exception:
            pass

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="ignore").lower()
        if "ruff" in text:
            evidence["python"].append("ruff configured")
        if "pytest" in text:
            evidence["python"].append("pytest configured")

    stack = max(scores, key=scores.get)
    if scores[stack] == 0:
        # Small migrated projects/benchmarks may not have a dependency manifest.
        # Infer from code extensions as a safe fallback.
        inferred = detect_by_extension(root)
        if inferred:
            stack = inferred
            evidence[stack].append("inferred from source file extensions")
        else:
            stack = "unknown"

    return {
        "stack": stack,
        "confidence": min(1.0, scores.get(stack, 0) / 4.0) if stack != "unknown" else 0.0,
        "scores": scores,
        "evidence": evidence.get(stack, []),
        "root": str(root),
    }

def _tool(name: str) -> Optional[str]:
    return shutil.which(name)

def _run(root: Path, name: str, command: list[str], *, required: bool = True,
         category: str = "validation", timeout: int = 300) -> CheckResult:
    started = time.monotonic()
    executable = command[0]
    if not _tool(executable):
        return CheckResult(
            name=name, command=command, status="unavailable", return_code=None,
            duration_seconds=0.0, required=required, category=category,
            stderr=f"Executable '{executable}' is not installed.",
        )
    try:
        proc = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout,
            env={**os.environ, "CI": "1", "PYTHONUNBUFFERED": "1"},
        )
        duration = round(time.monotonic() - started, 3)
        return CheckResult(
            name=name,
            command=command,
            status="passed" if proc.returncode == 0 else "failed",
            return_code=proc.returncode,
            duration_seconds=duration,
            stdout=_safe_text(proc.stdout),
            stderr=_safe_text(proc.stderr),
            required=required,
            category=category,
        )
    except subprocess.TimeoutExpired as exc:
        return CheckResult(
            name=name, command=command, status="failed", return_code=124,
            duration_seconds=round(time.monotonic() - started, 3),
            stdout=_safe_text(exc.stdout or ""), stderr=_safe_text(exc.stderr or "Timed out."),
            required=required, category=category,
        )
    except Exception as exc:
        return CheckResult(
            name=name, command=command, status="failed", return_code=1,
            duration_seconds=round(time.monotonic() - started, 3),
            stderr=str(exc), required=required, category=category,
        )

def _python_checks(root: Path) -> list[tuple[str, list[str], bool, str]]:
    checks = [
        ("python-compile", ["python", "-m", "compileall", "-q", "."], True, "syntax"),
    ]
    if _tool("ruff"):
        checks.append(("ruff", ["ruff", "check", "."], True, "lint"))
    elif _tool("python"):
        checks.append(("ruff", ["python", "-m", "ruff", "check", "."], False, "lint"))
    if _tool("pytest"):
        checks.append(("pytest", ["pytest", "-q"], True, "test"))
    else:
        checks.append(("pytest", ["python", "-m", "pytest", "-q"], False, "test"))
    if _tool("mypy") or _tool("python"):
        checks.append(("mypy", ["mypy", "."], False, "typecheck"))
    return checks



def _repository_structure_checks(root: Path) -> list[tuple[str, list[str], bool, str]]:
    """Reject ambiguous/contaminated target trees before release."""
    files = [
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED_DIRS for part in p.relative_to(root).parts)
    ]
    seen: dict[str, Path] = {}
    errors: list[str] = []
    forbidden_prefixes = ("__MACOSX/",)
    for p in files:
        rel = p.relative_to(root).as_posix()
        if rel.startswith(forbidden_prefixes) or p.name in {".DS_Store", "Thumbs.db"} or p.name.startswith("._"):
            errors.append(f"contaminated archive artifact: {rel}")
        key = rel.casefold()
        prior = seen.get(key)
        if prior and prior != p:
            errors.append(f"case-insensitive path collision: {prior.relative_to(root)} vs {rel}")
        seen[key] = p
    if not errors:
        return []
    # Use an inline Python command so this check does not depend on the host
    # project's internal module path.
    msg = "\\n".join(errors[:50]).replace("\\", "\\\\").replace("'", "\\'")
    return [(
        "repository-structure",
        ["python", "-c", f"raise SystemExit({msg!r})"],
        True,
        "structure",
    )]

def _node_repository_checks(root: Path) -> list[tuple[str, list[str], bool, str]]:
    """Static Node repository integrity checks that do not depend on an LLM.

    These catch the class of migration failures where translated symbols exist but
    imports/exports/paths do not compose into an executable repository.
    """
    checks: list[tuple[str, list[str], bool, str]] = []
    package = root / "package.json"
    if not package.exists():
        return checks

    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except Exception:
        return [("node-package-json", ["python", "-c", "import json; json.load(open('package.json'))"], True, "structure")]

    scripts = data.get("scripts") or {}
    test_files = [
        p for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"}
        and not any(part in IGNORED_DIRS for part in p.relative_to(root).parts)
        and (".test." in p.name.lower() or ".spec." in p.name.lower()
             or p.name.lower().startswith("test_") or p.name.lower().endswith("_test.js"))
    ]
    if test_files and "test" not in scripts:
        checks.append((
            "node-test-command",
            ["python", "-c", "raise SystemExit('package.json contains test files but no scripts.test')"],
            True,
            "test",
        ))

    # A package with source files should expose a runnable entry point or module
    # contract. Missing scripts are not inherently failures, but malformed local
    # imports and exports are.
    source_files = [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"}
        and not any(part in IGNORED_DIRS for part in p.relative_to(root).parts)
    ]
    if source_files:
        checks.append((
            "node-import-resolution",
            ["python", "-c", "from app.infrastructure.utils.post_migration_engine import check_node_repository_integrity; import sys; sys.exit(0 if check_node_repository_integrity('.') else 1)"],
            True,
            "structure",
        ))
    return checks


def _node_import_candidates(specifier: str, source: Path) -> list[Path]:
    if not specifier.startswith("."):
        return []
    base = (source.parent / specifier).resolve()
    candidates = [base]
    for ext in (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json"):
        candidates.append(Path(str(base) + ext))
    if base.is_dir():
        candidates.extend(base / f"index{ext}" for ext in (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"))
    return candidates


def check_node_repository_integrity(root: str | Path) -> bool:
    """Check local import paths and obvious export/require mismatches.

    This is deliberately conservative: it does not attempt to interpret all
    JavaScript module semantics. It catches unresolved relative imports and the
    common CommonJS/ESM export mismatch that broke the smoke-test migration.
    """
    root = Path(root).resolve()
    files = [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"}
        and not any(part in IGNORED_DIRS for part in p.relative_to(root).parts)
    ]
    errors: list[str] = []
    local_imports = re.compile(r"""(?:require\s*\(\s*['"]([^'"]+)['"]\s*\)|(?:from|import)\s+['"]([^'"]+)['"])""")
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in local_imports.finditer(text):
            spec = match.group(1) or match.group(2)
            if not spec or not spec.startswith("."):
                continue
            if not any(p.exists() for p in _node_import_candidates(spec, path)):
                errors.append(f"{path.relative_to(root)} -> unresolved local import {spec}")

        # Detect a file that both exports ESM syntax and assigns module.exports.
        has_esm = bool(re.search(r"\bexport\s+(?:default\s+)?(?:function|class|const|let|var|\{)", text))
        has_cjs = "module.exports" in text or "exports." in text
        if has_esm and has_cjs:
            errors.append(f"{path.relative_to(root)} -> mixed CommonJS and ESM exports")

        # Detect multiple module.exports assignments, which commonly overwrite
        # earlier symbol exports.
        if len(re.findall(r"\bmodule\.exports\s*=", text)) > 1:
            errors.append(f"{path.relative_to(root)} -> multiple module.exports assignments")

    return not errors

def _node_checks(root: Path) -> list[tuple[str, list[str], bool, str]]:
    package = root / "package.json"
    scripts = {}
    if package.exists():
        try:
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
        except Exception:
            pass
    checks: list[tuple[str, list[str], bool, str]] = []
    if (root / "package-lock.json").exists():
        checks.append(("npm-ci", ["npm", "ci"], True, "install"))
    elif (root / "pnpm-lock.yaml").exists() and _tool("pnpm"):
        checks.append(("pnpm-install", ["pnpm", "install", "--frozen-lockfile"], True, "install"))
    if "lint" in scripts:
        checks.append(("npm-lint", ["npm", "run", "lint"], True, "lint"))
    if "test" in scripts:
        checks.append(("npm-test", ["npm", "test", "--", "--runInBand"], True, "test"))
    if "build" in scripts:
        checks.append(("npm-build", ["npm", "run", "build"], True, "build"))
    checks.extend(_node_repository_checks(root))
    return checks

def _java_checks(root: Path) -> list[tuple[str, list[str], bool, str]]:
    if (root / "mvnw").exists():
        mvn = "./mvnw"
    else:
        mvn = "mvn"
    if (root / "pom.xml").exists():
        return [("maven-test", [mvn, "-B", "test"], True, "test"),
                ("maven-package", [mvn, "-B", "-DskipTests", "package"], True, "build")]
    gradle = "./gradlew" if (root / "gradlew").exists() else "gradle"
    return [("gradle-test", [gradle, "test"], True, "test"),
            ("gradle-build", [gradle, "build"], True, "build")]

def _go_checks(root: Path) -> list[tuple[str, list[str], bool, str]]:
    return [
        ("gofmt", ["sh", "-c", "test -z \"$(gofmt -l .)\""], True, "format"),
        ("go-vet", ["go", "vet", "./..."], True, "lint"),
        ("go-test", ["go", "test", "./..."], True, "test"),
        ("go-build", ["go", "build", "./..."], True, "build"),
    ]

def _php_checks(root: Path) -> list[tuple[str, list[str], bool, str]]:
    checks = [("composer-validate", ["composer", "validate", "--no-check-publish"], True, "lint")]
    if (root / "composer.lock").exists():
        checks.append(("composer-install", ["composer", "install", "--no-interaction", "--prefer-dist"], True, "install"))
    for p in root.rglob("*.php"):
        if any(part in IGNORED_DIRS for part in p.parts):
            continue
        checks.append((f"php-lint:{p.relative_to(root)}", ["php", "-l", str(p.relative_to(root))], True, "syntax"))
    if (root / "vendor" / "bin" / "phpunit").exists():
        checks.append(("phpunit", ["vendor/bin/phpunit", "--testdox"], True, "test"))
    return checks[:80]

def _dotnet_checks(root: Path) -> list[tuple[str, list[str], bool, str]]:
    return [
        ("dotnet-restore", ["dotnet", "restore"], True, "install"),
        ("dotnet-build", ["dotnet", "build", "--no-restore"], True, "build"),
        ("dotnet-test", ["dotnet", "test", "--no-build"], True, "test"),
    ]

def checks_for_stack(root: Path, stack: str) -> list[tuple[str, list[str], bool, str]]:
    """Resolve validation through the registered language adapter.

    Repository-level invariants remain language-agnostic; ecosystem commands are
    owned by the adapter. This is the single extension point for new languages.
    """
    adapter = get_adapter(stack)
    if not adapter:
        return _repository_structure_checks(root)
    return _repository_structure_checks(root) + adapter.checks(root) + (
        _node_repository_checks(root) if stack == "node" else []
    )

def generate_ci_workflow(root: Path, stack: str) -> Optional[Path]:
    if stack == "unknown":
        return None
    ci_dir = root / ".github" / "workflows"
    ci_dir.mkdir(parents=True, exist_ok=True)
    ci = ci_dir / "migration-quality.yml"
    if ci.exists():
        return ci

    adapter = get_adapter(stack)
    if not adapter:
        return None
    setup = adapter.ci_template
    content = """name: Migration Quality Gate

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""" + setup
    ci.write_text(content, encoding="utf-8")
    return ci

def _collect_repair_context(results: list[CheckResult]) -> str:
    failures = [r for r in results if r.status in {"failed", "unavailable"} and r.required]
    chunks = []
    for r in failures[:8]:
        chunks.append(
            f"CHECK: {r.name}\nCOMMAND: {' '.join(r.command)}\n"
            f"EXIT: {r.return_code}\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
        )
    return "\n\n".join(chunks)

def _repair_with_agno(root: Path, stack: str, results: list[CheckResult], attempt: int) -> dict[str, Any]:
    if os.getenv("POST_MIGRATION_AUTO_REPAIR", "true").lower() not in {"1", "true", "yes", "on"}:
        return {"attempt": attempt, "status": "disabled"}

    failures = [r for r in results if r.status == "failed" and r.required]
    if not failures:
        return {"attempt": attempt, "status": "not_needed"}

    try:
        from agno.agent import Agent
        from agno.tools.file import FileTools
        from app.infrastructure.agents_backend.model_provider import model

        agent = Agent(
            name="Migration Repair Agent",
            model=model,
            markdown=True,
            # Keep FileTools construction version-tolerant across Agno 2.x.
            # The toolkit's built-in defaults expose read/save/replace/list/search
            # capabilities; older/newer Agno releases have changed individual
            # enable_* constructor flags. Passing those flags here caused the
            # repair loop to fail before the agent could inspect the project.
            tools=[FileTools(base_dir=root)],
            instructions=[
                "You are a senior migration repair engineer.",
                "You may ONLY edit files inside the supplied base directory using FileTools.",
                "Do not delete files. Do not change unrelated architecture.",
                "Make the smallest deterministic fixes that address the validation failures.",
                "Never hide a failure by weakening tests, lint rules, or CI.",
                "Preserve public APIs and business behavior.",
                "After edits, summarize changed files and why.",
            ],
            debug_mode=False,
        )
        prompt = f"""
Repair attempt {attempt} for target stack: {stack}.

The migrated project is already generated. Validation failed.
Use FileTools to inspect the relevant files and make minimal fixes.

{_collect_repair_context(results)}

Important:
- Do not invent dependencies unless the error proves one is required.
- Do not remove or skip tests.
- Do not modify CI merely to make it green.
- Keep the project executable and idiomatic for {stack}.
"""
        response = agent.run(prompt)
        return {
            "attempt": attempt,
            "status": "completed",
            "summary": str(getattr(response, "content", response))[-5000:],
        }
    except Exception as exc:
        logger.exception("Agno repair attempt failed")
        return {"attempt": attempt, "status": "failed", "error": str(exc)}

def repair_behavioral_mismatch(
    migrated_root: str | Path,
    *,
    stack: str,
    probe_report: dict[str, Any],
    attempt: int = 1,
) -> dict[str, Any]:
    """Run one bounded Agno repair pass using behavioral probe evidence.

    This deliberately reuses the same FileTools-only repair agent as the quality
    gate. Behavioral evidence is presented as a failed validation check; the
    normal quality gates must still pass after the repair.
    """
    root = Path(migrated_root).resolve()
    results = [CheckResult(
        name="behavioral-probes",
        command=["migration-behavioral-probe"],
        status="failed",
        return_code=1,
        duration_seconds=0.0,
        required=True,
        category="behavior",
        stderr=json.dumps(probe_report, indent=2)[:12000],
    )]
    return _repair_with_agno(root, stack, results, attempt)


def validate_migrated_project(
    migrated_root: str | Path,
    *,
    migration_name: str = "",
    max_repair_attempts: int = 2,
    persist: bool = True,
    progress_callback=None,
) -> dict[str, Any]:
    root = Path(migrated_root).resolve()
    if not root.exists() or not root.is_dir():
        return {"status": "not_ready", "message": "Migrated project directory does not exist.", "path": str(root)}

    stack_info = detect_target_stack(root)
    stack = stack_info["stack"]
    if progress_callback:
        progress_callback("engineering", 72, "Detecting target stack")
    ci_path = generate_ci_workflow(root, stack)
    if progress_callback:
        progress_callback("engineering", 76, "Generating CI quality gate")

    attempts: list[dict[str, Any]] = []
    final_results: list[CheckResult] = []

    if stack == "unknown":
        status = "blocked"
        message = "Could not identify a supported target ecosystem."
    else:
        for attempt in range(max_repair_attempts + 1):
            checks = checks_for_stack(root, stack)
            if progress_callback:
                progress_callback("engineering", 80, f"Running validation gates (attempt {attempt + 1})")
            results = []
            for idx, (name, cmd, required, category) in enumerate(checks, 1):
                results.append(_run(root, name, cmd, required=required, category=category))
                if progress_callback and checks:
                    pct = 80 + int((idx / len(checks)) * 8)
                    progress_callback("engineering", min(pct, 88), f"{category.title()}: {name}")
            final_results = results

            required_failures = [r for r in results if r.required and r.status in {"failed", "unavailable"}]
            if not required_failures:
                attempts.append({"attempt": attempt, "status": "passed"})
                status = "passed"
                message = "All required validation gates passed."
                break

            attempts.append({
                "attempt": attempt,
                "status": "failed",
                "failures": [r.name for r in required_failures],
            })
            if attempt >= max_repair_attempts:
                status = "blocked"
                message = "Validation gates remain red after the configured repair budget."
                break

            if progress_callback:
                progress_callback("engineering", 90, f"AI repair pass {attempt + 1}")
            repair = _repair_with_agno(root, stack, results, attempt + 1)
            attempts[-1]["repair"] = repair
            if repair.get("status") != "completed":
                status = "blocked"
                message = "Validation failed and the Agno repair loop could not complete."
                break

    passed = sum(1 for r in final_results if r.status == "passed")
    required = sum(1 for r in final_results if r.required)
    score = round((passed / required) * 100, 2) if required else (100.0 if status == "passed" else 0.0)

    report = {
        "status": status,
        "message": message,
        "migration_name": migration_name,
        "project_path": str(root),
        "target_stack": stack_info,
        "quality_score": score,
        "release_ready": status == "passed",
        "ci_workflow": str(ci_path.relative_to(root)) if ci_path else None,
        "attempts": attempts,
        "checks": [asdict(r) for r in final_results],
        "generated_at_epoch": time.time(),
    }

    if persist:
        report_dir = root / ".migration"
        report_dir.mkdir(exist_ok=True)
        (report_dir / "quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        md = [
            "# Post-Migration Quality Report",
            "",
            f"- **Status:** {status}",
            f"- **Release ready:** {report['release_ready']}",
            f"- **Target stack:** {stack}",
            f"- **Quality score:** {score}/100",
            "",
            "## Validation Gates",
            "",
            "| Gate | Status | Duration |",
            "| --- | --- | ---: |",
        ]
        for r in final_results:
            md.append(f"| `{r.name}` | {r.status} | {r.duration_seconds:.2f}s |")
        md += ["", "## Repair Attempts", ""]
        for a in attempts:
            md.append(f"- Attempt {a.get('attempt')}: **{a.get('status')}**")
        (report_dir / "quality_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    return report
