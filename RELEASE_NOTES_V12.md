# v12 — Smoke-Test Hardened Migration Pipeline

## Fixes
- Planning steps now recover symbol/module metadata directly from the source KB when Agno workflow step state is unavailable.
- Dependency prediction validates and repairs `package.json`; invalid `^` placeholders are converted to valid npm ranges and Express targets receive only the required Express runtime dependency.
- Local source-language detection no longer depends on the optional external SourceAnalyzer service.
- SourceAnalyzer is optional; blank `ANALYZER_API_URL` uses deterministic local static analysis.
- Universal Ctags ignores macOS `__MACOSX` and `._*` archive metadata.
- Post-migration reporting recognizes both `Migrated Code` and `migrated_code` output directories and can build a source comparison baseline from the source tree when legacy `source_response.json` is absent.
- Missing token-event DB tables are now created by SQLAlchemy startup initialization.
- Migration artifact persistence has an ORM fallback when legacy PostgreSQL stored procedures are absent.
- Streamlit migration history tolerates string migration names returned by the API.

## Validation
- 22/22 automated tests pass.
- Python compilation passes.
- Streamlit compilation passes.
- Docker build/run must still be validated in the user's Docker environment.
