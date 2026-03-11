"""
OSINT Platform – FastAPI application entry point.

Registers all routers, middleware, error handlers, and lifespan hooks.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings, setup_logging

setup_logging()
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise and tear down application-level resources."""
    logger.info("Starting OSINT Platform backend (env=%s)", settings.ENVIRONMENT)

    # ── Database engine warm-up ────────────────────────────────────────────
    from storage.database.postgres import async_engine
    async with async_engine.begin() as conn:
        await conn.run_sync(lambda _: None)  # verify connectivity
    logger.info("PostgreSQL connection pool ready")

    # ── Redis ──────────────────────────────────────────────────────────────
    from storage.cache.redis_adapter import RedisAdapter
    redis = RedisAdapter(settings.REDIS_URL)
    await redis.connect()
    app.state.redis = redis
    logger.info("Redis connection established")

    # ── Plugin / Module system ─────────────────────────────────────────────
    from plugins.loader import load_all_plugins
    await load_all_plugins(app)
    logger.info("Plugin system initialised")

    yield  # ──────────────── application is running ────────────────

    # ── Teardown ───────────────────────────────────────────────────────────
    logger.info("Shutting down OSINT Platform backend")
    await redis.close()
    await async_engine.dispose()
    logger.info("All connections closed")


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="OSINT Platform API",
        description=(
            "Production-grade Open-Source Intelligence platform.\n\n"
            "Provides entity resolution, graph analysis, case management, "
            "and multi-source data ingestion."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ──────────────────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        response.headers["X-Process-Time"] = f"{elapsed:.4f}s"
        return response

    # ── Rate-limiting middleware ───────────────────────────────────────────
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        # Skip rate limiting for health-check and docs
        if request.url.path in {"/health", "/docs", "/redoc", "/openapi.json"}:
            return await call_next(request)

        redis = getattr(request.app.state, "redis", None)
        if redis is not None:
            client_ip = request.client.host if request.client else "unknown"
            key = f"rate_limit:{client_ip}:{int(time.time() // 60)}"
            try:
                count = await redis.increment(key)
                if count == 1:
                    await redis.expire(key, 60)
                if count > settings.RATE_LIMIT_PER_MINUTE:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "detail": "Rate limit exceeded. Please retry after 60 seconds.",
                            "retry_after": 60,
                        },
                        headers={"Retry-After": "60"},
                    )
            except Exception:
                # Never block a request because Redis is unavailable
                pass

        return await call_next(request)

    # ── Routers ───────────────────────────────────────────────────────────
    _register_routers(app)

    # ── Error handlers ────────────────────────────────────────────────────
    _register_error_handlers(app)

    # ── Health check ──────────────────────────────────────────────────────
    @app.get(
        "/health",
        tags=["system"],
        summary="Health check",
        response_description="Service health status",
    )
    async def health_check() -> dict:
        return {"status": "ok", "version": "1.0.0", "environment": settings.ENVIRONMENT}

    return app


def _register_routers(app: FastAPI) -> None:
    """Dynamically import and register API v1 routers."""
    from api.v1.routes.auth import router as auth_router
    from api.v1.routes.ingest import router as ingest_router
    from api.v1.routes.entities import router as entities_router
    from api.v1.routes.relationships import router as relationships_router
    from api.v1.routes.graph import router as graph_router
    from api.v1.routes.search import router as search_router
    from api.v1.routes.cases import router as cases_router
    from api.v1.routes.export import router as export_router

    prefix = "/api/v1"

    app.include_router(auth_router, prefix=prefix, tags=["auth"])
    app.include_router(ingest_router, prefix=prefix, tags=["ingest"])
    app.include_router(entities_router, prefix=prefix, tags=["entities"])
    app.include_router(relationships_router, prefix=prefix, tags=["relationships"])
    app.include_router(graph_router, prefix=prefix, tags=["graph"])
    app.include_router(search_router, prefix=prefix, tags=["search"])
    app.include_router(cases_router, prefix=prefix, tags=["cases"])
    app.include_router(export_router, prefix=prefix, tags=["export"])


def _register_error_handlers(app: FastAPI) -> None:
    from fastapi.exceptions import RequestValidationError
    from fastapi import HTTPException

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        logger.warning(
            "HTTP %s at %s: %s",
            exc.status_code,
            request.url.path,
            exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("Validation error at %s: %s", request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Request validation failed",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"Resource not found: {request.url.path}"},
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception at %s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred. Please try again later."},
        )


app = create_app()
