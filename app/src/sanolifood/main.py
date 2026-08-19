import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sanolifood import __version__
from sanolifood.core.config import get_settings
from sanolifood.core.logging import configure_logging
from sanolifood.database.session import engine
from sanolifood.schema_guard import schema_status
from sanolifood.web.audit import router as audit_router
from sanolifood.web.auth import router as auth_router
from sanolifood.web.dependencies import AuthenticationRequired, PermissionDenied
from sanolifood.web.inventory import router as inventory_router
from sanolifood.web.production import router as production_router
from sanolifood.web.quality import router as quality_router
from sanolifood.web.router import router as web_router
from sanolifood.web.templates import templates, view_context
from sanolifood.web.users import router as users_router


settings = get_settings()
configure_logging(settings.log_level, settings.app_log_file)
logger = logging.getLogger("sanolifood")
container_root = Path("/app")
project_dir = container_root if (container_root / "static").is_dir() else Path(__file__).resolve().parents[2]


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
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret.get_secret_value(),
    session_cookie="sanolifood_session",
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=settings.app_env == "production",
)
app.mount("/static", StaticFiles(directory=str(project_dir / "static")), name="static")
app.include_router(auth_router)
app.include_router(web_router)
app.include_router(users_router)
app.include_router(audit_router)
app.include_router(inventory_router)
app.include_router(production_router)
app.include_router(quality_router)


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
    if request.url.path.startswith("/static/") and settings.app_env in {"development", "test"}:
        response.headers["Cache-Control"] = "no-store, max-age=0"
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
    _, missing_tables = schema_status(engine)
    if missing_tables:
        logger.error(
            "readiness_schema_incomplete",
            extra={
                "event_type": "platform.readiness.failed",
                "missing_tables": sorted(missing_tables),
            },
        )
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "reason": "database_schema_incomplete",
                "missing_tables": sorted(missing_tables),
            },
        )
    return {"status": "ready", "database": "reachable", "version": __version__}


@app.exception_handler(AuthenticationRequired)
async def authentication_required(_: Request, __: AuthenticationRequired) -> RedirectResponse:
    return RedirectResponse(url="/auth/login", status_code=303)


@app.exception_handler(PermissionDenied)
async def permission_denied(request: Request, exc: PermissionDenied) -> HTMLResponse:
    current_user = getattr(request.state, "current_user", None)
    return templates.TemplateResponse(
        request=request,
        name="errors/403.html",
        context=view_context(
            request,
            page_title="Acceso restringido",
            current_user=current_user,
            nav_active="",
            error_message=exc.message,
        ),
        status_code=403,
    )


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
