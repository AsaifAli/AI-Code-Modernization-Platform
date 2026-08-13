# Release Evidence

The post-migration pipeline is intentionally evidence-driven. A migration is not considered release-ready merely because an LLM reports success.

## Gates

1. Import normalization
2. Semantic/contract verification
3. Deterministic security review
4. Lint/type checks/tests/build
5. Bounded Agno repair and re-validation
6. Architecture/dependency analysis
7. Provenance and source→target traceability
8. Release packaging

## Evidence artifacts

- `.migration/security_review.json` — deterministic secret/high-risk pattern review.
- `.migration/provenance_manifest.json` — source/target SHA-256 file hashes, model/tool metadata and gate statuses.
- `.migration/traceability_matrix.json` — source-to-target contract evidence and unresolved mappings.
- `.migration/semantic_verification.json` — contract, test and behavioral probe evidence.
- `.migration/dependency_topology.json` — dependency cardinality, fan-in/fan-out and migration sizing policy.

## Security scope

The built-in scanner is intentionally conservative and deterministic. It is not a replacement for dedicated SAST, secret-management or dependency-vulnerability products. Critical embedded secrets block release; high-risk code patterns are surfaced for human review.

## Reproducibility

The provenance manifest records the configured model identifier and SHA-256 hashes of source/target code files. Exact deterministic replay still depends on model/provider determinism and external dependencies; the platform does not claim bit-for-bit AI reproducibility.
