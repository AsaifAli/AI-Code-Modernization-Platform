# LegacyLens deployment readiness

## Deployment topology

The Render Blueprint defines two web services:

- `ai-code-modernization-api` — FastAPI migration/agent service.
- `ai-code-modernization-ui` — Streamlit developer workbench.

The public demo uses the shared Portfolio LLM Gateway and Qdrant. The Render manifest does not provision a Qdrant cluster, so its endpoint and credentials must be supplied separately.

## Current service state

A live check of the previously used Render API and UI hostnames returned Render's **"This service has been suspended by its owner"** response. The source code and deployment manifest remain in the repository, but the hosted application is not currently available at those hostnames. Re-enable or recreate the Render services and confirm their generated URLs before presenting LegacyLens as a live hosted demo.

## Required external configuration

On the API service, configure:

- `QDRANT_URL`
- `QDRANT_API_KEY`
- Shared Gateway connectivity as defined in `render.yaml`
- Correct `ALLOWED_ORIGINS` matching the deployed UI URL

The UI receives `AGENT_SERVICE_URL` from the API service reference in the Blueprint. The website-launched one-time BYOK handoff also requires `PORTFOLIO_SESSION_GATEWAY_URL` on the UI service and a valid Gateway session contract.

Do not configure a persistent SQL database for the lightweight Render demo topology unless the deployment design is deliberately changed. Task state may be process-local and disposable when `DATABASE_URL` is absent.

## Re-enable and verify

After reactivating the two services:

1. Confirm the API `/healthz` endpoint returns HTTP 200.
2. Confirm API `/readyz` returns `status: ready`.
3. Confirm the UI `/_stcore/health` route responds and the UI can reach the API.
4. Upload a small synthetic repository.
5. Run scan and migration planning.
6. Run a small migration and inspect syntax/QA gates.
7. Download the artifact during the active session.
8. Launch from the studio website and verify one-time Gateway handoff.

## Demo limitations

The Render demo is suitable for portfolio demonstrations, not production migration workloads. Without persistent database configuration, task state and runtime files are disposable. Download generated artifacts during the active session. Semantic equivalence of migrated code still requires human review and project-specific validation.
