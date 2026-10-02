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
)
