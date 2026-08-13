# Security Notes

## Secrets

`.env` is not part of the portfolio repository. Use `.env.example` as the configuration template.

Never place API keys, database passwords, JWT secrets or personal access tokens in source files, notebooks, screenshots or benchmark fixtures.

If an old clone ever contained a real credential, rotate it even if the file has since been deleted.

## Git provider tokens

GitHub/GitLab tokens are accepted only at the integration boundary and are not copied into returned user metadata. Self-hosted GitLab discovery is configured through `GITLAB_SELF_HOSTED_BASE_URL`.

## File-system boundaries

Migration workspaces should be mounted under the application-managed `Temp`/shared workspace. For production deployments, enforce canonical-path checks, archive traversal protection, file-count limits and maximum upload sizes before processing untrusted repositories.

## Authentication

Standalone mode can derive a stable local identity from a bearer token for development. This is not a production identity provider. Multi-user deployments should place the service behind OIDC/JWT validation and enforce authorization at the migration/task level.

## Model endpoints

Provider endpoints and credentials are configuration-driven. Avoid logging prompts, access tokens or sensitive repository contents by default.
