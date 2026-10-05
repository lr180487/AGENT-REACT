"""
routes_health.py

Endpoints de salud del sistema.

Endpoints finales debido a:

    app.include_router(
        health_router,
        prefix="/api/v1"
    )

Quedan:

    GET /api/v1/health
    GET /api/v1/health/live
    GET /api/v1/health/ready
    GET /api/v1/health/db
    GET /api/v1/health/redis

Objetivo:

    - Liveness: comprobar que FastAPI está funcionando.
    - Readiness: comprobar si la aplicación está preparada.
    - DB: comprobar PostgreSQL.
    - Redis: comprobar Redis / Upstash.
    - Health general: resumen de servicios.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings


router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


# ============================================================
# Helpers
# ============================================================

def utc_now() -> str:
    """Devuelve timestamp UTC ISO-8601."""

    return datetime.now(
        timezone.utc
    ).isoformat()


def service_result(
    service: str,
    status: str,
    *,
    latency_ms: float | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Construye una respuesta homogénea."""

    result: dict[str, Any] = {
        "service": service,
        "status": status,
    }

    if latency_ms is not None:
        result["latency_ms"] = round(
            latency_ms,
            2
        )

    if error:
        result["error"] = error

    return result


# ============================================================
# Liveness
# ============================================================

@router.get(
    "",
    summary="Estado general de la API",
)
async def health() -> dict[str, Any]:
    """
    Health general.

    No depende de PostgreSQL, Redis ni del proveedor LLM.

    Sirve para comprobar que FastAPI está levantado.
    """

    return {
        "status": "ok",
        "service": getattr(
            settings,
            "APP_NAME",
            "agente_react_rag",
        ),
        "version": getattr(
            settings,
            "VERSION",
            "1.0.0",
        ),
        "environment": getattr(
            settings,
            "ENV",
            "development",
        ),
        "timestamp": utc_now(),
    }


# ============================================================
# Liveness probe
# ============================================================

@router.get(
    "/live",
    summary="Liveness probe",
)
async def liveness() -> dict[str, Any]:
    """
    Kubernetes/Docker liveness probe.

    Si responde correctamente significa que
    el proceso FastAPI está vivo.
    """

    return {
        "status": "alive",
        "timestamp": utc_now(),
    }


# ============================================================
# PostgreSQL
# ============================================================

async def check_database() -> dict[str, Any]:
    """
    Comprueba la conexión PostgreSQL.

    Se intenta importar la infraestructura de DB de forma
    tolerante porque el proyecto puede ejecutarse inicialmente
    en modo mock/demo.
    """

    database_url = getattr(
        settings,
        "DATABASE_URL",
        None,
    )

    if not database_url:
        return service_result(
            "postgresql",
            "not_configured",
        )

    started = time.perf_counter()

    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import (
            create_async_engine,
        )

        # Normalizar URL PostgreSQL para SQLAlchemy async.
        async_url = database_url

        if async_url.startswith(
            "postgresql://"
        ):
            async_url = async_url.replace(
                "postgresql://",
                "postgresql+asyncpg://",
                1,
            )

        if async_url.startswith(
            "postgresql+psycopg://"
        ):
            async_url = async_url.replace(
                "postgresql+psycopg://",
                "postgresql+asyncpg://",
                1,
            )

        engine = create_async_engine(
            async_url,
            pool_pre_ping=True,
        )

        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT 1")
            )

        await engine.dispose()

        latency = (
            time.perf_counter() - started
        ) * 1000

        return service_result(
            "postgresql",
            "ok",
            latency_ms=latency,
        )

    except ImportError as exc:

        return service_result(
            "postgresql",
            "not_available",
            error=(
                "Dependencia async no instalada: "
                f"{exc}"
            ),
        )

    except Exception as exc:

        latency = (
            time.perf_counter() - started
        ) * 1000

        return service_result(
            "postgresql",
            "error",
            latency_ms=latency,
            error=str(exc),
        )


# ============================================================
# Redis / Upstash
# ============================================================

async def check_redis() -> dict[str, Any]:
    """
    Comprueba Redis.

    Compatible conceptualmente con:

        REDIS_URL=redis://localhost:6379/0

    o una URL Redis/Upstash configurada mediante
    REDIS_URL.
    """

    redis_url = getattr(
        settings,
        "REDIS_URL",
        None,
    )

    if not redis_url:
        redis_url = os.getenv(
            "UPSTASH_REDIS_URL"
        )

    if not redis_url:
        return service_result(
            "redis",
            "not_configured",
        )

    started = time.perf_counter()

    try:
        import redis.asyncio as redis

        client = redis.from_url(
            redis_url,
            decode_responses=True,
        )

        pong = await client.ping()

        await client.aclose()

        latency = (
            time.perf_counter() - started
        ) * 1000

        return service_result(
            "redis",
            "ok" if pong else "error",
            latency_ms=latency,
        )

    except ImportError as exc:

        return service_result(
            "redis",
            "not_available",
            error=(
                "Instala redis: "
                f"{exc}"
            ),
        )

    except Exception as exc:

        latency = (
            time.perf_counter() - started
        ) * 1000

        return service_result(
            "redis",
            "error",
            latency_ms=latency,
            error=str(exc),
        )


# ============================================================
# Database endpoint
# ============================================================

@router.get(
    "/db",
    summary="Estado de PostgreSQL",
)
async def database_health():
    """Comprueba específicamente PostgreSQL."""

    result = await check_database()

    status_code = (
        200
        if result["status"] == "ok"
        else 503
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "timestamp": utc_now(),
            **result,
        },
    )


# ============================================================
# Redis endpoint
# ============================================================

@router.get(
    "/redis",
    summary="Estado de Redis / Upstash",
)
async def redis_health():
    """Comprueba específicamente Redis/Upstash."""

    result = await check_redis()

    status_code = (
        200
        if result["status"] == "ok"
        else 503
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "timestamp": utc_now(),
            **result,
        },
    )


# ============================================================
# Readiness
# ============================================================

@router.get(
    "/ready",
    summary="Readiness probe",
)
async def readiness():
    """
    Comprueba si la aplicación está preparada.

    Actualmente comprueba:

        - PostgreSQL
        - Redis

    El LLM no se consulta aquí para evitar generar
    una llamada externa/coste simplemente por un health check.
    """

    started = time.perf_counter()

    database = await check_database()
    redis = await check_redis()

    dependencies = {
        "postgresql": database,
        "redis": redis,
    }

    # Estados que no bloquean necesariamente el arranque
    # cuando el proyecto se ejecuta en modo demo.
    environment = getattr(
        settings,
        "ENV",
        "development",
    )

    if environment == "development":

        blocking_statuses = {
            "error",
        }

    else:

        blocking_statuses = {
            "error",
            "not_configured",
            "not_available",
        }

    failed = [
        name
        for name, result in dependencies.items()
        if result["status"] in blocking_statuses
    ]

    total_latency = (
        time.perf_counter() - started
    ) * 1000

    is_ready = len(failed) == 0

    response = {
        "status": (
            "ready"
            if is_ready
            else "not_ready"
        ),
        "timestamp": utc_now(),
        "environment": environment,
        "latency_ms": round(
            total_latency,
            2,
        ),
        "dependencies": dependencies,
    }

    if failed:
        response["failed_dependencies"] = failed

    return JSONResponse(
        status_code=200 if is_ready else 503,
        content=response,
    )