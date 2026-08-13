# Portfolio-ready change log

This distribution was prepared as a public portfolio repository.

## Security / hygiene

- Removed committed `.env` and replaced it with `.env.example`.
- Removed Git history from the distributable archive so old secrets cannot be accidentally republished from this copy.
- Removed development notebooks, local machine paths, private IP references and backup artifacts.
- Made self-hosted GitLab integration configuration-driven.
- Prevented GitHub/GitLab access tokens from being copied into returned user metadata.
- Added a repository quality gate for forbidden artifacts, Python syntax and common secret/internal-address leaks.

## Engineering quality

- Added lightweight regression tests.
- Added deterministic migration evaluation harness with optional executable benchmark tests.
- Added example benchmark fixture and results.
- Added CI for hygiene, syntax compilation and tests.
- Added FastAPI `/healthz` liveness and `/readyz` readiness endpoints.
- Added request correlation IDs and structured application logging.
- Added migration-name path-traversal validation.
- Hardened Docker containers to run non-root with dropped Linux capabilities.
- Added Docker health checks and healthy dependency ordering.
- Improved JSON chunker behavior to avoid empty chunks and removed direct `print()` noise.
- Removed hard-coded OpenAI model ID and provider placeholders from the runtime factory.

## Documentation

- Reworked the root README around architecture, engineering decisions, evaluation and security.
- Added architecture, evaluation, security and engineering-decision documents.
- Added benchmark guidance and a production-readiness boundary document.

## Intentionally not claimed

This distribution does not claim semantic equivalence of migrated code. The evaluation harness reports deterministic structural signals; production-grade benchmark evidence should add target-language compilation and automated test execution.

## Post-migration release engineering

The platform now demonstrates a full migration-to-release lifecycle rather than code generation alone. After conversion it detects the target ecosystem, generates a CI workflow, runs deterministic lint/syntax/test/build gates, and can invoke an Agno repair agent for a bounded number of remediation attempts. A migration is considered release-ready only when the required gates are green; otherwise the final ZIP is intentionally withheld.

The release gate produces machine-readable and human-readable quality reports under `.migration/` and adds stack-aware GitHub Actions CI to the migrated project when one is not already present.

## Flagship-level engineering loop

The platform now exposes the live Agno execution plan in the UI, runs post-migration engineering gates (CI, linting, syntax/type checks, tests, builds and bounded AI repair), and generates a migrated-code architecture intelligence page with a module diagram, technology profile and README-style analysis. Final packaging remains gated by the engineering quality result.


## Semantic & Behavioral Verification

Post-migration validation now includes an evidence-based semantic verification stage. It extracts public source and target contracts, normalizes symbol names across languages, checks callable arity where statically observable, inventories target tests, and executes the target test runner when supported. The result is persisted under `.migration/semantic_verification.json` and `.migration/semantic_verification.md`.

This is intentionally presented as **evidence of behavioral compatibility**, not a claim of formal semantic equivalence. Missing/renamed symbols and signature mismatches are surfaced before release, while passing target tests provide executable evidence.
