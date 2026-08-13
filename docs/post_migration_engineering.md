# Post-Migration Engineering Gate

## Purpose

The platform treats migration as an engineering lifecycle:

1. Scan the source.
2. Build the knowledge base.
3. Plan the target architecture.
4. Convert symbols/files.
5. Detect the target ecosystem.
6. Run executable quality gates.
7. Use bounded AI-assisted repair when a gate fails.
8. Re-run the gates.
9. Generate CI and evidence artifacts.
10. Publish the ZIP only when the release gate is green.

## Supported validation adapters

| Stack | Gates
| --- | ---
| Python | compileall, Ruff when available, pytest, optional mypy
| Node.js | lockfile-aware install, npm lint/test/build scripts
| Java | Maven/Gradle test and build
| Go | gofmt, go vet, go test, go build
| PHP | composer validation/install, PHP syntax lint, PHPUnit when present
| .NET | dotnet restore, build, test

If a project has no dependency manifest, the detector falls back to source-file extensions. Unknown ecosystems are blocked rather than silently marked as successful.

## AI repair loop

The repair agent is an Agno `Agent` equipped with the built-in `FileTools` toolkit. It receives the failed validation output and is instructed to make minimal edits without deleting files, weakening tests, or changing CI merely to hide failures. The deterministic runner then executes the allow-listed validation commands again.

The repair budget defaults to two attempts and can be configured with `POST_MIGRATION_MAX_REPAIR_ATTEMPTS`. Set `POST_MIGRATION_AUTO_REPAIR=false` to disable the AI repair stage while retaining deterministic validation.

## Release policy

A green quality gate produces:

- `.migration/quality_report.json`
- `.migration/quality_report.md`
- `.github/workflows/migration-quality.yml` when CI is absent
- existing migration risk/comparison reports
- showcase artifacts
- final processed ZIP

A red gate produces diagnostic reports but **does not publish the release ZIP**. This is important for a portfolio demonstration: the platform is not merely generating code and declaring success; it is enforcing a release criterion.

## Security boundary

Validation commands are selected by the platform's stack adapters and are not supplied by the LLM. The repair agent can edit files through Agno `FileTools`, but it is not given arbitrary shell execution. For production use with untrusted repositories, command execution should be moved to an isolated disposable sandbox such as a container/job runner or an external code-execution service.

## Agno design

The implementation keeps Agno at the center of orchestration. The project uses `Workflow`, `Step`, `WorkflowTools`, and the built-in `FileTools` toolkit. This aligns the platform with Agno's current agent/workflow model while keeping deterministic validation outside the model's control loop.
