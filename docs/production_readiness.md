# Production-readiness boundary

This repository is intentionally positioned as a **portfolio-grade engineering system**, not as a claim that it is a drop-in enterprise production platform.

## Implemented hardening

- Secrets are externalized through `.env.example`.
- Public distribution contains no Git history.
- Migration identifiers reject path traversal and filesystem-ambiguous names.
- Request IDs are returned in `X-Request-ID` and included in application logs.
- Liveness (`/healthz`) and readiness (`/readyz`) endpoints are exposed.
- Docker containers run as a non-root user.
- Compose services drop Linux capabilities and disable privilege escalation.
- Background task status is persisted when the database is configured; interrupted tasks are explicitly marked failed on startup.
- Repository quality/security checks run in CI.

## Remaining production work

For a real multi-tenant deployment, the next layer should include:

1. OIDC/OAuth2-backed authentication and authorization.
2. Durable job execution with a queue/worker model instead of process-local `BackgroundTasks` execution.
3. Alembic-managed schema migrations, including the legacy/raw SQL tables currently expected by the application.
4. Per-tenant storage isolation and signed artifact download URLs.
5. Upload size limits, archive traversal protection and filesystem sandboxing.
6. Rate limiting and concurrency controls around expensive LLM workflows.
7. OpenTelemetry traces and a metrics backend for latency, retries, tokens and cost.
8. KMS/secret-manager integration rather than environment variables for production secrets.
9. Language-specific compile/build/test adapters for migration validation.

The portfolio README should present these as the **production roadmap**, not as capabilities that are already complete.
