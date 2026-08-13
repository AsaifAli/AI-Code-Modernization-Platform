# Release Notes — v12.3

## Migration correctness and release-safety hardening

This release fixes the failures exposed by the Python → JavaScript smoke test.

### Fixed

- Knowledge-base ingestion no longer requires optional `project_graph.test_hierarchy_stats`.
- Missing hierarchy statistics no longer prevent symbols, modules, dependencies, and file paths from being ingested.
- Fixed threshold logging when no hierarchy-threshold document exists.
- Structured dependency artifacts are parsed structurally. `package.json` JSON syntax is never interpreted as package names.
- Dependency extraction now correctly reports `express` instead of `{`, `}`, and JSON property lines.
- Migration-plan verification now requires at least one real source-symbol plan.
- Conversion refuses to run when the migration plan is empty or contains only a dependency-file sentinel.
- Release packaging refuses to create a ZIP when there are no source-symbol migration plans.

### Safety invariant

A migration can no longer be presented as release-ready merely because a dependency file or empty artifact exists. The release ZIP requires a real symbol migration plan and a green post-migration quality gate.

### Validation

- Python compilation: passed
- Targeted regression tests: 16 passed
- Added regression coverage for dependency parsing and release packaging gates.
