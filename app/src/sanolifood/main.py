import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sanolifood import __version__
from sanolifood.core.config import get_settings
from sanolifood.core.logging import configure_logging
from sanolifood.database.session import engine
from sanolifood.web.router import router as web_router


settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("sanolifood")
project_dir = Path("/app") if Path("/app/static").is_dir() else Path(__file__).resolve().parents[2]


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "application_started",
        extra={"event_type": "platform.lifecycle.started", "app_version": __version__, "environment": settings.app_env},
    )
    yield
    engine.dispose()
    logger.info("application_stopped", extra={"event_type": "platform.lifecycle.stopped"})


app = FastAPI(
    title="SanoliFood Operations API",
    version=__version__,
    docs_url="/api/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.app_env in {"development", "test"} else settings.allowed_hosts_list,
)
app.mount("/static", StaticFiles(directory=str(project_dir / "static")), name="static")
app.include_router(web_router)


@app.middleware("http")
async def request_context(request: Request, call_next):
    started = time.perf_counter()
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    logger.info(
        "request_completed",
        extra={
            "event_type": "http.request.completed",
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "source_ip": request.headers.get("X-Real-IP")
            or (request.client.host if request.client else "unknown"),
            "forwarded_for": request.headers.get("X-Forwarded-For"),
            "user_agent": request.headers.get("User-Agent"),
        },
    )
    return response


@app.get("/health", tags=["platform"])
@app.get("/health/live", tags=["platform"])
def liveness() -> dict[str, str]:
    return {"status": "ok", "service": "sanolifood-app", "version": __version__}


@app.get("/health/ready", tags=["platform"])
def readiness() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready", "database": "reachable", "version": __version__}


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.exception(
        "unhandled_exception",
        extra={"event_type": "application.error.unhandled", "correlation_id": correlation_id, "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "correlation_id": correlation_id},
        headers={"X-Correlation-ID": correlation_id},
    )
