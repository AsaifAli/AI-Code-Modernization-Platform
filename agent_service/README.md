# Agent Service

FastAPI backend and workflow runtime for the AI Code Modernization Platform.

## Responsibilities

- repository scanning and program analysis
- knowledge-base construction and retrieval
- migration planning
- agentic code conversion
- post-migration comparison and risk reporting
- task lifecycle persistence when PostgreSQL is configured
- REST/workflow event stream-facing workflow events

## Local development

```bash
python -m pip install -r requirements.txt
python main.py
```

The API listens on port `8015` by default. Swagger is available at `/docs` and the lightweight liveness endpoint is `/healthz`.

## Configuration

Configuration is environment-driven. Copy the repository root `.env.example` to `.env` and provide the model/database settings required by your environment.

Do not commit `.env`, credentials, model tokens or private repository URLs.

## Docker

The service Dockerfile installs Universal CTags and the native dependencies required by the scanner/DB stack. Runtime migration state is mounted at `/app/Temp` by Docker Compose.
