# Render Free Deployment

## Public topology

Browser -> Streamlit UI -> FastAPI agent service -> Supabase Postgres + OpenRouter

The local Docker Compose stack remains unchanged for full development, including LiteLLM, local Postgres, and optional vLLM.

## Free-tier architecture decisions

- Both Render services use the Free web-service tier.
- The API uses Supabase Postgres instead of another Render Free Postgres database.
- This avoids Render's one-Free-Postgres-per-workspace limitation and its 30-day Free Postgres lifetime.
- Runtime artifacts are written to the container filesystem and are therefore disposable. The demo expects users to download results during the active session.

## Required Render secrets

Set these on `ai-code-modernization-api`:

- `OPENAI_API_KEY` = OpenRouter API key
- `DATABASE_URL` = Supabase Postgres connection string

Use Supabase's IPv4-compatible pooler/session connection string for persistent backend traffic when connecting from Render.

## Important

Do not commit `DATABASE_URL` or `OPENAI_API_KEY` to GitHub. Put them only in Render environment variables.

## First deployment test

1. API `/healthz`
2. UI loads
3. UI reports API connected
4. Upload a very small test repository
5. Run scan/plan first
6. Only then test the full migration workflow

The Free web services are suitable for portfolio/demo use, not production workloads.
