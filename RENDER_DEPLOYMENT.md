# Render Free Deployment

## Public topology

Browser → Streamlit UI → FastAPI agent service → LLM Gateway + Qdrant

The public Render deployment does not require a persistent SQL database. The agent service treats database access as optional: when `DATABASE_URL` is not configured, database initialization is skipped and task status falls back to process-local memory.

Runtime files and task state on the Render instance are disposable. Users should download migration artifacts during the active session.

The local Docker Compose stack remains available for full development and can continue using PostgreSQL for durable local testing.

## Required Render secrets

Set these on `ai-code-modernization-api`:

- `QDRANT_URL` = Qdrant endpoint
- `QDRANT_API_KEY` = Qdrant API key

The public service uses the shared Portfolio LLM Gateway. Do not configure `DATABASE_URL` for the Render demo.

Do not commit secrets to GitHub. Put them only in Render environment variables.

## Deployment verification

1. API `/healthz` returns HTTP 200.
2. API `/readyz` returns `status: ready`.
3. UI loads and reports the API as connected.
4. Upload a very small test repository.
5. Run scan/plan first.
6. Test a small migration.
7. Download the generated artifact during the same session.

The Free web service is suitable for portfolio/demo use, not production workloads.
