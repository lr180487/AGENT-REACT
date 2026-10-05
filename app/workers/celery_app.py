<<<<<<< HEAD
from __future__ import annotations
from celery import Celery
from app.config import settings

broker = settings.CELERY_BROKER_URL or settings.REDIS_URL
if not broker:
    raise RuntimeError("Configura CELERY_BROKER_URL o REDIS_URL para usar Celery")

celery_app = Celery(
    "agente_react_rag",
    broker=broker,
    backend=settings.CELERY_RESULT_BACKEND or broker,
    include=["app.workers.agent_tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=settings.AGENT_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.AGENT_TASK_TIME_LIMIT,
    broker_connection_retry_on_startup=True,
=======

"""
app/workers/celery_app.py

Configuración de workers para AGENT-REACT.

Arquitectura:

FastAPI
   │
   ├── Celery ───────────────► Upstash Redis
   │
   └── QStash ───────────────► FastAPI webhook
                                  │
                                  ▼
                               Celery
                                  │
                                  ▼
                             Agent Worker

QStash NO reemplaza el broker de Celery.
QStash se utiliza para tareas HTTP diferidas,
programadas, retries y workflows.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from celery import Celery

from app.config import (
    settings,
    get_redis_url,
    get_celery_broker_url,
    get_celery_backend_url,
)


logger = logging.getLogger(__name__)


# ============================================================
# REDIS / CELERY
# ============================================================

REDIS_URL = get_redis_url()

CELERY_BROKER_URL = get_celery_broker_url()

CELERY_RESULT_BACKEND = get_celery_backend_url()


# ============================================================
# VALIDACIÓN
# ============================================================

if not CELERY_BROKER_URL:

    raise RuntimeError(
        """
        CELERY_BROKER_URL no está configurado.

        Configura:

        UPSTASH_REDIS_URL=rediss://...
        """
    )


if not CELERY_RESULT_BACKEND:

    logger.warning(
        "CELERY_RESULT_BACKEND no configurado. "
        "Se utilizará el broker como backend."
    )

    CELERY_RESULT_BACKEND = CELERY_BROKER_URL


# ============================================================
# CELERY APP
# ============================================================

celery_app = Celery(
    "agent_react",

    broker=CELERY_BROKER_URL,

    backend=CELERY_RESULT_BACKEND,

    include=[
        "app.workers.agent_tasks",
    ],
)


# ============================================================
# CELERY CONFIGURATION
# ============================================================

celery_app.conf.update(

    # --------------------------------------------------------
    # Serialización
    # --------------------------------------------------------

    task_serializer="json",

    result_serializer="json",

    accept_content=[
        "json",
    ],


    # --------------------------------------------------------
    # Resultados
    # --------------------------------------------------------

    result_expires=3600,

    task_track_started=True,


    # --------------------------------------------------------
    # ACK / IDMPOTENCIA
    # --------------------------------------------------------

    task_acks_late=True,

    task_reject_on_worker_lost=True,

    worker_prefetch_multiplier=1,


    # --------------------------------------------------------
    # Retry broker
    # --------------------------------------------------------

    broker_connection_retry_on_startup=True,

    broker_connection_max_retries=10,


    # --------------------------------------------------------
    # Timeouts
    # --------------------------------------------------------

    task_soft_time_limit=(
        settings.AGENT_TASK_SOFT_TIME_LIMIT
    ),

    task_time_limit=(
        settings.AGENT_TASK_TIME_LIMIT
    ),


    # --------------------------------------------------------
    # Retry
    # --------------------------------------------------------

    task_default_retry_delay=(
        settings.AGENT_TASK_RETRY_DELAY
    ),

    task_max_retries=(
        settings.AGENT_TASK_MAX_RETRIES
    ),
)


# ============================================================
# QSTASH CONFIGURATION
# ============================================================

QSTASH_TOKEN: Optional[str] = getattr(
    settings,
    "QSTASH_TOKEN",
    None,
)

QSTASH_URL: str = getattr(
    settings,
    "QSTASH_URL",
    "https://qstash.upstash.io",
)

QSTASH_CURRENT_SIGNING_KEY: Optional[str] = getattr(
    settings,
    "QSTASH_CURRENT_SIGNING_KEY",
    None,
)

QSTASH_NEXT_SIGNING_KEY: Optional[str] = getattr(
    settings,
    "QSTASH_NEXT_SIGNING_KEY",
    None,
)


# ============================================================
# QSTASH STATUS
# ============================================================

def qstash_enabled() -> bool:
    """
    Indica si QStash está configurado.
    """

    return bool(
        QSTASH_TOKEN
    )


# ============================================================
# QSTASH HEADERS
# ============================================================

def qstash_headers() -> dict[str, str]:
    """
    Headers necesarios para comunicarse con QStash.
    """

    if not QSTASH_TOKEN:

        raise RuntimeError(
            "QSTASH_TOKEN no está configurado."
        )

    return {
        "Authorization": (
            f"Bearer {QSTASH_TOKEN}"
        ),

        "Content-Type": (
            "application/json"
        ),
    }


# ============================================================
# QSTASH PUBLISH
# ============================================================

def qstash_publish(
    destination: str,
    body: dict[str, Any],
    *,
    delay: Optional[str] = None,
    retries: int = 3,
    callback: Optional[str] = None,
) -> dict[str, Any]:
    """
    Publica un mensaje en QStash.

    Parameters
    ----------
    destination:
        URL HTTPS pública que recibirá el mensaje.

    body:
        Payload JSON.

    delay:
        Ejemplo:
            "10s"
            "5m"
            "1h"

    retries:
        Número de reintentos QStash.

    callback:
        URL opcional para callback.

    Nota:
        Esta función utiliza HTTP contra QStash.
    """

    if not qstash_enabled():

        raise RuntimeError(
            "QStash no está configurado. "
            "Define QSTASH_TOKEN."
        )

    import requests

    url = (
        f"{QSTASH_URL.rstrip('/')}"
        f"/v2/publish/"
        f"{destination}"
    )

    headers = qstash_headers()

    headers[
        "Upstash-Retry-Count"
    ] = str(retries)

    if delay:
        headers[
            "Upstash-Delay"
        ] = delay

    if callback:
        headers[
            "Upstash-Callback"
        ] = callback

    response = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# CELERY TASK HELPER
# ============================================================

def enqueue_agent_task(
    task_name: str,
    payload: dict[str, Any],
    *,
    countdown: Optional[int] = None,
    eta=None,
):
    """
    Ejecuta una tarea Celery.

    Uso:

        enqueue_agent_task(
            "app.workers.agent_tasks.run_agent",
            {
                "message": "Analizar ventas"
            }
        )
    """

    options: dict[str, Any] = {}

    if countdown is not None:
        options["countdown"] = countdown

    if eta is not None:
        options["eta"] = eta

    return celery_app.send_task(
        task_name,
        kwargs=payload,
        **options,
    )


# ============================================================
# QSTASH → CELERY
# ============================================================

def qstash_schedule_agent(
    callback_url: str,
    payload: dict[str, Any],
    *,
    delay: Optional[str] = None,
    retries: int = 3,
) -> dict[str, Any]:
    """
    Programa una ejecución de AGENT-REACT mediante QStash.

    QStash:
        delay / delivery / retry

    FastAPI:
        recibe webhook

    Celery:
        ejecuta procesamiento pesado
    """

    return qstash_publish(
        destination=callback_url,
        body=payload,
        delay=delay,
        retries=retries,
    )


# ============================================================
# LOGGING
# ============================================================

logger.info(
    "Celery inicializado"
)

logger.info(
    "Celery broker: %s",
    (
        "CONFIGURADO"
        if CELERY_BROKER_URL
        else "NO CONFIGURADO"
    ),
)

logger.info(
    "Celery backend: %s",
    (
        "CONFIGURADO"
        if CELERY_RESULT_BACKEND
        else "NO CONFIGURADO"
    ),
)

logger.info(
    "QStash: %s",
    (
        "CONFIGURADO"
        if qstash_enabled()
        else "NO CONFIGURADO"
    ),
>>>>>>> ebbf022 (feat: complete Agent ReAct architecture)
)
