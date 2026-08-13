# Flagship Capability Model

The platform is intentionally positioned as a **migration engineering system**, not a code-translation demo.

## End-to-end lifecycle

1. **Discover** — inspect source structure, technology, dependencies and architecture signals.
2. **Plan** — produce an explicit migration plan before code generation.
3. **Transform** — convert the repository using Agno-orchestrated agents/workflows.
4. **Observe** — stream the actual Agno workflow plan and stage progress to the UI.
5. **Engineer** — install dependencies, lint, syntax-check, type-check where available, test and build.
6. **Repair** — use a bounded Agno repair agent with FileTools to fix actionable failures.
7. **Analyze** — inspect the migrated repository and produce architecture/dependency intelligence.
8. **Prove** — generate CI and quality evidence; block release when required gates remain red.
9. **Package** — produce the final ZIP only after the release gate is green.

## Post-migration intelligence

Every successful migrated repository can contain:

- `.migration/quality_report.json`
- `.migration/quality_report.md`
- `.migration/architecture_analysis.json`
- `.migration/architecture_analysis.md`
- `.github/workflows/migration-quality.yml`

The architecture analysis is deterministic and based on repository structure plus language-aware import/include signals. It is deliberately labeled as static inference rather than pretending to be a complete runtime call graph.

## Why this is stronger for a portfolio

The flagship story becomes: **AI performs the migration, deterministic engineering gates verify it, bounded AI repair closes the loop, and the platform produces auditable evidence plus an executable release artifact.**

This demonstrates agent orchestration, software architecture, CI/CD, test automation, static analysis, observability, artifact generation and responsible AI boundaries in one project.
