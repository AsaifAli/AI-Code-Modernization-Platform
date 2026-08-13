"""Zips the converted 'Migrated Code' output into <migration_name>_processed.zip
so /v1/migration/status and /v1/migration/download have something to find.

Plain filesystem operation, not an agent/LLM step — called directly by the
orchestrator after the migration workflow completes, not wired in as an
Agno Step.
"""
import logging
import shutil
import zipfile
from pathlib import Path

from app.infrastructure.utils.Constants.migration_workflow import MigrationWorkflowStrings

logger = logging.getLogger(__name__)


def package_migrated_code(migration_dir: Path, migration_name: str) -> str:
    """Zip migration_dir/'Migrated Code' into migration_dir/<migration_name>_processed.zip.

    Returns a short human-readable status string; never raises — packaging
    failures are logged and reported in the returned string instead, since a
    packaging error shouldn't be treated as a migration failure.
    """
    migrated_code_dir = migration_dir / "Migrated Code"

    if not migrated_code_dir.exists() or not any(migrated_code_dir.iterdir()):
        return "No converted files found under 'Migrated Code' — skipped zip packaging"

    # Defense-in-depth release gate: a dependency file alone is never a valid
    # migrated project. Require at least one actual source-symbol plan.
    plan_path = migration_dir / "migration_plan.json"
    if not plan_path.exists():
        return "Migration plan missing — skipped zip packaging"
    try:
        import json
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        symbol_plan_count = sum(
            1
            for module_data in plan.values() if isinstance(module_data, dict)
            for item in (module_data.get("plans", []) or [])
            if isinstance(item, dict) and item.get("symbol_id") not in {None, "", "dependency_file"}
        )
        if symbol_plan_count == 0:
            return "No source-symbol migration plans found — skipped zip packaging"
    except Exception as exc:
        logger.warning("Unable to validate migration plan before packaging: %s", exc)
        return "Invalid migration plan — skipped zip packaging"

    zip_base = migration_dir / f"{migration_name}{MigrationWorkflowStrings.ZIP_SUFFIX}"
    try:
        # Build the archive explicitly so macOS metadata and ambiguous paths can
        # never leak into a release artifact.
        zip_path = Path(str(zip_base))
        if zip_path.suffix.lower() != ".zip":
            zip_path = zip_path.with_suffix(".zip")
        forbidden_names = {".DS_Store", "Thumbs.db"}
        files = []
        seen: set[str] = set()
        for path in migrated_code_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(migrated_code_dir).as_posix()
            if rel.startswith("__MACOSX/") or path.name.startswith("._") or path.name in forbidden_names:
                continue
            key = rel.casefold()
            if key in seen:
                return f"Ambiguous target paths detected — skipped zip packaging: {rel}"
            seen.add(key)
            files.append((path, rel))

        if not files:
            return "No valid converted source files found after archive sanitization — skipped zip packaging"

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, rel in files:
                archive.write(path, rel)

        logger.info(MigrationWorkflowStrings.ZIP_LOG.format(user_id=migration_name, zip_path=zip_path))
        return f"Packaged converted project -> {zip_path}"
    except Exception as exc:
        logger.exception("Failed to zip converted output for migration '%s'", migration_name)
        return f"Failed to package converted project: {exc}"
