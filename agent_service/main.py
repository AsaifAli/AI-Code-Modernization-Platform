import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

# Patch Agno Agent.run for token metrics before any Agent instances are created via imports.
# from app.infrastructure.utils.agent_token_bootstrap import install_agent_token_hooks

# install_agent_token_hooks()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from pydantic import ValidationError

from app.infrastructure.utils.http_middleware import RequestIdMiddleware
from app.infrastructure.utils.logger import configure_logging
from app.infrastructure.db.db_connection import engine, init_db
from app.infrastructure.repositories.task_repository import mark_orphaned_running_tasks_as_failed
from app.infrastructure.utils.Constants.app_constants import ServiceConstants, AgentConstants
from app.presentation.routes.agent_router import router as agent_router
from app.presentation.routes.folder_structure_router import router as folder_structure_router

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize persistence and recovery state for the service."""
    if engine is not None:
        try:
            init_db()
            logger.info("Database tables verified/created (ORM-declared models only).")
        except Exception:
            logger.exception(
                "init_db() failed; ORM-declared tables (users, models, "
                "migration_artifacts, agent_tasks, prompts, prompt_types) may be missing. "
                "Tables accessed via raw SQL/reflection elsewhere (e.g. "
                "migration_data, migration_scan_result, migration_llm_token_events, "
                "migration_diagrams) are NOT covered by init_db() and must already "
                "exist in the target database."
            )
    else:
        logger.warning("DB not configured; skipping init_db().")

    try:
        orphaned = mark_orphaned_running_tasks_as_failed()
        if orphaned:
            logger.warning(
                "Marked %d task(s) stuck in 'running' as failed — they were "
                "interrupted by a previous agent_service restart.", orphaned,
            )
    except Exception:
        logger.exception("Failed to sweep orphaned running tasks at startup")

    yield


app = FastAPI(
    title="Agent Orchestrator Service",
    version="0.1.0",
    description="Executes AI agent teams on demand",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:8722").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz", tags=["system"])
async def healthz():
    """Liveness endpoint; process is running and able to serve HTTP."""
    return {"status": "ok", "service": "agent_service", "version": "0.1.0"}


@app.get("/readyz", tags=["system"])
async def readyz():
    """Readiness endpoint reporting whether configured infrastructure is reachable."""
    database_ok = False
    if engine is not None:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            database_ok = True
        except Exception:
            logger.exception("Readiness database check failed")
    checks = {"database_configured": engine is not None, "database_reachable": database_ok}
    ready = database_ok if engine is not None else True
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


app.include_router(agent_router)
app.include_router(folder_structure_router, prefix=ServiceConstants.MIGRATION_SERVICE_PREFIX)


@app.exception_handler(ValidationError)
async def validation_handler(_, exc: ValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def general_exception_handler(_, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": AgentConstants.INTERNAL_SERVER_ERROR})


if __name__ == "__main__":
    SERVICE_HOST = os.getenv("SERVICE_HOST", "localhost")
    AGENT_SERVICE_PORT = int(os.getenv("AGENT_SERVICE_PORT", 8015))
    uvicorn_log_level = os.getenv("LOG_LEVEL", "info")
    logger.info("Starting agent_service")
    import uvicorn

    uvicorn.run(
        ServiceConstants.AGENT_ENDPOINT,
        host=SERVICE_HOST,
        port=AGENT_SERVICE_PORT,
        log_level=uvicorn_log_level,
    )

