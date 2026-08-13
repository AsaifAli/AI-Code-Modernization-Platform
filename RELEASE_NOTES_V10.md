# v10 — Containerized Tooling & Startup Hardening

## Fixed

- Removed stale `process_target_scanner_output_to_response` and `scan_target_project` imports from the post-migration pipeline. Those helpers no longer exist in the current scanner implementation and were preventing `agent_service` from starting.
- Replaced the obsolete target-scanner stage with the current architecture/semantic analysis and target knowledge-base indexing path.
- Made Universal Ctags container-first: the agent image installs `universal-ctags`, while application code resolves `CTAGS_BIN` from PATH automatically.
- `CTAGS_BIN` is now an optional executable name/path override rather than a required host-specific path.
- Added clearer Ctags discovery diagnostics and validation of the resolved executable.

## Validation

- `pytest -q`: 22 passed.
- `python -m compileall -q agent_service`: passed.
- Docker image build could not be executed in the current build environment because the Docker CLI is unavailable; the supplied `agent_service/Dockerfile` installs `universal-ctags` and validates it through PATH at runtime.

## Recommended next flagship features

1. Migration provenance manifest and deterministic replay.
2. Source-to-target symbol traceability with clickable evidence.
3. Secret/license/security scanning as a release gate.
4. Rollback/checkpoint support for AI repair attempts.
5. Cost/latency/token observability per migration stage.
6. Human approval gates for high-risk architectural changes.
