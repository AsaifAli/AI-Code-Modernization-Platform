import logging
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from app.infrastructure.utils.file_utils import get_migration_directory
from app.infrastructure.utils.showcase_manager import generate_showcase_bundle
from app.infrastructure.utils.reporting_manager import generate_migration_comparison_report
from app.infrastructure.utils.migration_context import migration_name_ctx, source_path_ctx
from app.infrastructure.utils.post_migration_engine import validate_migrated_project, detect_target_stack, repair_behavioral_mismatch, _repair_with_agno, CheckResult
from app.infrastructure.utils.migrated_architecture_analyzer import analyze_migrated_architecture
from app.infrastructure.utils.import_normalizer import normalize_imports_in_tree
from app.infrastructure.utils.dependency_topology import build_dependency_topology_report
from app.infrastructure.utils.semantic_verifier import verify_migration_semantics
from app.infrastructure.utils.task_progress import publish_progress
from app.infrastructure.utils.migration_evidence import security_scan, provenance_manifest, traceability_matrix

logger = logging.getLogger(__name__)


def run_post_migration_pipeline(
    migration_name: str,
    migrated_code_path: Optional[str] = None,
    *,
    persist: bool = True,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    migration_dir = get_migration_directory(migration_name=migration_name, source_path="")
    # Conversion writes to "Migrated Code"; older builds used "migrated_code".
    # Accept both so the post-migration gate works across existing runs.
    candidates = [
        Path(migrated_code_path) if migrated_code_path else None,
        migration_dir / "Migrated Code",
        migration_dir / "migrated_code",
    ]
    migrated_root = next((p for p in candidates if p and p.exists() and p.is_dir()), candidates[1])
    if not migrated_root.exists() or not migrated_root.is_dir():
        return {
            "status": "not_ready",
            "message": "Migrated Code output path not found",
            "migration_name": migration_name,
            "migrated_code_path": str(migrated_root),
        }

    logger.info("Post migration pipeline started for %s", migration_name)

    # Symbol-wise conversion appends generated fragments. Normalize imports
    # before lint/build so imports from later symbols cannot remain below code.
    publish_progress("analysis", 88, "Normalizing generated imports and module headers")
    import_normalization = normalize_imports_in_tree(migrated_root)

    # Build an auditable relationship report when the source AST artifact is
    # available. This captures one-to-many, many-to-one and many-to-many
    # relationships without pretending LOC itself defines cardinality.
    topology = {"status": "not_available"}
    ast_candidates = [
        migration_dir / "ast_output" / "syntactic_ast.json",
        migration_dir / "syntactic_ast.json",
        Path("ast_output") / "syntactic_ast.json",
    ]
    ast_path = next((p for p in ast_candidates if p.exists()), None)
    if ast_path:
        topology = build_dependency_topology_report(
            ast_path,
            migration_dir / ".migration" / "dependency_topology.json",
        )

    # The repair loop owns semantic verification. Start with an empty report so
    # the first loop cycle observes the current target state, and any repair
    # decision is based on that first evidence. Every subsequent cycle then
    # revalidates semantics after the repair edits.
    try:
        source_root = Path(source_path_ctx.get("")) if source_path_ctx.get("") else None
    except Exception:
        source_root = None
    semantic_verification: Dict[str, Any] = {}

    # Deterministic security review is evidence, not an AI opinion. Critical
    # secret findings block release; high-risk code patterns require review.
    publish_progress("security", 89, "Scanning migrated code for secrets and high-risk patterns")
    security = security_scan(migrated_root, persist=persist)
    if security.get("status") == "blocked":
        provenance = provenance_manifest(migration_name, source_path_ctx.get(""), migrated_root, {"status":"blocked"}, semantic_verification, security, persist=persist)
        traceability = traceability_matrix(semantic_verification, migrated_root if persist else None)
        return {"status":"blocked","migration_name":migration_name,"migrated_code_path":str(migrated_root),"security":security,"semantic_verification":semantic_verification,"provenance":provenance,"traceability":traceability,"message":"Release blocked by critical security findings."}

    # Unified post-migration repair loop. Deterministic quality failures and
    # semantic/behavioral failures are both actionable inputs to the Agno repair
    # agent. After every edit we rerun BOTH layers of evidence before deciding
    # whether the repository is releasable.
    max_repair_attempts = max(0, int(os.getenv("POST_MIGRATION_MAX_REPAIR_ATTEMPTS", "3")))
    repair_history = []
    quality_gate = {"status": "blocked", "release_ready": False}
    semantic_verification = semantic_verification

    for cycle in range(max_repair_attempts + 1):
        publish_progress("engineering", 72 + min(cycle, max_repair_attempts) * 4,
                         f"Validating migrated project (cycle {cycle + 1}/{max_repair_attempts + 1})")

        quality_gate = validate_migrated_project(
            migrated_root,
            migration_name=migration_name,
            # The outer loop owns the repair budget. The inner validator must
            # only run deterministic checks and must not consume the same budget.
            max_repair_attempts=0,
            persist=persist,
            progress_callback=publish_progress,
        )

        # Re-run semantic verification AFTER every repair. A prior semantic
        # report is never trusted after target files have changed.
        semantic_verification = verify_migration_semantics(
            source_root, migrated_root, migration_name=migration_name, persist=persist
        )

        semantic_status = semantic_verification.get("status")
        semantic_blocked = semantic_status != "verified"
        deterministic_blocked = quality_gate.get("status") != "passed"

        if not deterministic_blocked and not semantic_blocked:
            quality_gate["semantic_gate"] = {"status": "passed", "semantic_status": semantic_status}
            quality_gate["release_ready"] = True
            quality_gate["status"] = "passed"
            quality_gate["repair_history"] = repair_history
            break

        if cycle >= max_repair_attempts:
            quality_gate["semantic_gate"] = {
                "status": "blocked" if semantic_blocked else "passed",
                "semantic_status": semantic_status,
                "contract_coverage": (semantic_verification.get("contract") or {}).get("coverage_percent"),
                "test_execution": (semantic_verification.get("execution") or {}).get("status"),
                "behavioral_status": (semantic_verification.get("behavioral_probes") or {}).get("status"),
            }
            quality_gate["release_ready"] = False
            quality_gate["status"] = "blocked"
            quality_gate["message"] = (
                "Migration remains blocked after the configured repair budget. "
                "Deterministic or semantic validation evidence is still failing."
            )
            quality_gate["repair_history"] = repair_history
            break

        # Build one repair context from BOTH deterministic and semantic evidence.
        repair_results: list[CheckResult] = []
        for check in quality_gate.get("checks", []):
            if not isinstance(check, dict):
                continue
            if check.get("required") and check.get("status") in {"failed", "unavailable"}:
                repair_results.append(
                    CheckResult(
                        name=str(check.get("name", "validation")),
                        command=[str(x) for x in check.get("command", [])],
                        status=str(check.get("status", "failed")),
                        return_code=check.get("return_code"),
                        duration_seconds=float(check.get("duration_seconds", 0.0) or 0.0),
                        stdout=str(check.get("stdout", "") or ""),
                        stderr=str(check.get("stderr", "") or ""),
                        required=bool(check.get("required", True)),
                        category=str(check.get("category", "validation")),
                    )
                )
        if semantic_blocked:
            repair_results.append(
                CheckResult(
                    name="semantic-verification",
                    command=["migration-semantic-verification"],
                    status="failed",
                    required=True,
                    return_code=1,
                    duration_seconds=0.0,
                    stdout="",
                    stderr=json.dumps(semantic_verification, indent=2)[:16000],
                    category="semantic",
                )
            )

        stack = (quality_gate.get("target_stack") or {}).get("stack", "unknown")
        publish_progress("engineering", 90,
                         f"Agno repair pass {cycle + 1}: fixing validation failures")
        repair = _repair_with_agno(migrated_root, stack, repair_results, cycle + 1)
        repair_history.append({
            "cycle": cycle + 1,
            "deterministic_status": quality_gate.get("status"),
            "semantic_status": semantic_status,
            "repair": repair,
        })

        if repair.get("status") != "completed":
            quality_gate["status"] = "blocked"
            quality_gate["release_ready"] = False
            quality_gate["message"] = (
                f"Validation failed and Agno repair pass {cycle + 1} could not complete."
            )
            quality_gate["repair_history"] = repair_history
            break

        # Continue the loop; edits have happened, so both deterministic gates
        # and semantic verification must be rerun from the new filesystem state.

    # Persist the FINAL release decision after all repair/revalidation cycles.
    if persist:
        report_dir = migrated_root / ".migration"
        report_dir.mkdir(exist_ok=True)
        (report_dir / "quality_report.json").write_text(
            json.dumps(quality_gate, indent=2), encoding="utf-8"
        )

    if quality_gate.get("status") != "passed":
        security = security_scan(migrated_root, persist=persist)
        provenance = provenance_manifest(migration_name, source_path_ctx.get(""), migrated_root, quality_gate, semantic_verification, security, persist=persist)
        traceability = traceability_matrix(semantic_verification, migrated_root if persist else None)
        return {
            "status": "blocked",
            "migration_name": migration_name,
            "migrated_code_path": str(migrated_root),
            "quality_gate": quality_gate,
            "security": security,
            "semantic_verification": semantic_verification,
            "provenance": provenance,
            "traceability": traceability,
            "message": quality_gate.get("message") or "Post-migration release gate is red; final packaging is blocked.",
        }

    publish_progress("analysis", 93, "Building migrated-code architecture map")
    architecture = analyze_migrated_architecture(migrated_root, migration_name=migration_name, persist=persist)
    publish_progress("analysis", 95, "Analyzing target structure and dependencies")

    # The old target-scanner/response helpers were removed from the scanner
    # pipeline, but this post-migration path still referenced them.  Keep the
    # target-side KB build as the canonical post-migration indexing operation
    # and explicitly report the legacy scanner stage as skipped instead of
    # importing stale symbols at application startup.
    scan_result = {
        "status": "skipped",
        "reason": "target scanner helpers are superseded by architecture and semantic analysis",
        "target_path": str(migrated_root),
    }
    target_response_result = {
        "status": "not_required",
        "reason": "migrated-code-only reporting uses the generated target tree directly",
    }
    # The target tree is already the canonical post-migration artifact.
    # Do not rebuild the source KB here: the legacy KB helper has no public
    # build_kb_db API and doing so would couple release validation to an
    # unrelated indexing side effect.
    target_index = {"status": "not_required", "reason": "Architecture and semantic artifacts index the target tree directly."}

    provenance = provenance_manifest(migration_name, source_path_ctx.get(""), migrated_root, quality_gate, semantic_verification, security, persist=persist)
    traceability = traceability_matrix(semantic_verification, migrated_root if persist else None)

    report = generate_migration_comparison_report(
        migration_name=migration_name,
        persist=persist,
        include_markdown=False,
        require_migrated=False,
    )
    showcase = generate_showcase_bundle(migration_name=migration_name, persist=persist)

    return {
        "status": "ready",
        "migration_name": migration_name,
        "migrated_code_path": str(migrated_root),
        "scanner": {
            "scan_target_project": str(scan_result),
            "process_target_scanner_output": str(target_response_result),
            "target_index": target_index,
        },
        "quality_gate": quality_gate,
        "semantic_verification": semantic_verification,
        "report": report,
        "showcase": showcase,
        "architecture": architecture,
        "import_normalization": import_normalization,
        "dependency_topology": topology,
        "security": security,
        "provenance": provenance,
        "traceability": traceability,
    }


def run_migrated_code_quality_check(
    migration_name: str,
    migrated_code_path: Optional[str] = None,
) -> Dict[str, Any]:
    migration_dir = get_migration_directory(migration_name=migration_name, source_path="")
    candidates = [
        Path(migrated_code_path) if migrated_code_path else None,
        migration_dir / "Migrated Code",
        migration_dir / "migrated_code",
    ]
    migrated_root = next((p for p in candidates if p and p.exists() and p.is_dir()), candidates[1])
    if not migrated_root.exists() or not migrated_root.is_dir():
        return {
            "status": "not_ready",
            "message": "Migrated Code output path not found",
            "migration_name": migration_name,
            "migrated_code_path": str(migrated_root),
        }

    frontend_root = migrated_root / "frontend"
    backend_root = migrated_root / "backend"
    all_files = [p for p in migrated_root.rglob("*") if p.is_file()]
    frontend_files = [
        p for p in all_files if p.suffix.lower() in {".jsx", ".tsx", ".js", ".ts"} and "frontend" in str(p).lower()
    ]
    backend_files = [p for p in all_files if p.suffix.lower() in {".py", ".java", ".cs", ".go", ".js", ".ts"} and "backend" in str(p).lower()]

    issues: Dict[str, list] = {
        "html_in_frontend_components": [],
        "inline_sql_in_services": [],
        "empty_critical_folders": [],
        "large_files_context_risk": [],
        "repository_layer_missing_or_empty": [],
    }

    html_doc_patterns = re.compile(r"<!doctype|<html|<head|<body", re.IGNORECASE)
    sql_patterns = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b[\s\S]{0,200}\b(FROM|WHERE|INTO|SET)\b", re.IGNORECASE)

    for p in frontend_files:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            txt = ""
        if html_doc_patterns.search(txt):
            issues["html_in_frontend_components"].append(str(p))
        if len(txt) > 35000:
            issues["large_files_context_risk"].append({"file": str(p), "chars": len(txt)})

    for p in backend_files:
        low_path = str(p).lower()
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            txt = ""
        if any(k in low_path for k in ["service", "controller"]) and sql_patterns.search(txt):
            issues["inline_sql_in_services"].append(str(p))
        if len(txt) > 50000:
            issues["large_files_context_risk"].append({"file": str(p), "chars": len(txt)})

    # Critical folder checks
    critical_dirs = []
    if frontend_root.exists():
        critical_dirs.extend(
            [
                frontend_root / "src" / "components",
                frontend_root / "src" / "pages",
                frontend_root / "src" / "services",
            ]
        )
    if backend_root.exists():
        critical_dirs.extend(
            [
                backend_root / "services",
                backend_root / "repositories",
                backend_root / "models",
            ]
        )

    for d in critical_dirs:
        if not d.exists():
            issues["empty_critical_folders"].append({"folder": str(d), "reason": "missing"})
            continue
        has_files = any(x.is_file() for x in d.rglob("*"))
        if not has_files:
            issues["empty_critical_folders"].append({"folder": str(d), "reason": "empty"})

    # Repository layer presence
    repo_dirs = [p for p in migrated_root.rglob("*") if p.is_dir() and p.name.lower() in {"repo", "repos", "repository", "repositories"}]
    if not repo_dirs:
        issues["repository_layer_missing_or_empty"].append("No repository folder found")
    else:
        if not any(any(f.is_file() for f in d.rglob("*")) for d in repo_dirs):
            issues["repository_layer_missing_or_empty"].append("Repository folders exist but contain no files")

    total_issues = sum(len(v) for v in issues.values())
    score = 100
    score -= min(25, len(issues["html_in_frontend_components"]) * 5)
    score -= min(25, len(issues["inline_sql_in_services"]) * 5)
    score -= min(20, len(issues["empty_critical_folders"]) * 3)
    score -= min(15, len(issues["repository_layer_missing_or_empty"]) * 10)
    score -= min(15, len(issues["large_files_context_risk"]) * 2)
    score = max(0, score)

    recommendations = []
    if issues["html_in_frontend_components"]:
        recommendations.append("Replace full HTML document tags with valid JSX component structure.")
    if issues["inline_sql_in_services"]:
        recommendations.append("Move raw SQL from services/controllers into repository/data-access layer.")
    if issues["empty_critical_folders"]:
        recommendations.append("Populate missing/empty critical architecture folders with scaffold implementations.")
    if issues["repository_layer_missing_or_empty"]:
        recommendations.append("Create repository layer and route persistence access through it.")
    if issues["large_files_context_risk"]:
        recommendations.append("Split oversized files and apply bounded context generation for retry.")

    return {
        "status": "ready",
        "migration_name": migration_name,
        "migrated_code_path": str(migrated_root),
        "quality_score": score,
        "total_files": len(all_files),
        "issues": issues,
        "recommendations": recommendations,
    }

