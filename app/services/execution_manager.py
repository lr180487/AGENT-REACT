from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models_execution import AgentEvent, AgentRun


def now():
    return datetime.now(timezone.utc)


class RunNotFound(KeyError):
    pass


@dataclass
class ActiveRun:
    run_id: str
    task: asyncio.Task | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    disconnect_task: asyncio.Task | None = None


class ExecutionManager:
    """Coordina ejecuciones ReAct, cancelación y reconexión WebSocket.

    Los eventos son persistidos en PostgreSQL/SQLite y las ejecuciones activas se
    mantienen en memoria. Una desconexión no cancela inmediatamente: se concede
    una ventana de reconexión antes de cancelar la ejecución huérfana.
    """

    RECONNECT_GRACE_SECONDS = 30
    MAX_QUEUE = 256

    def __init__(self):
        self._runs: dict[str, ActiveRun] = {}
        self._lock = asyncio.Lock()

    def create_run(self, *, session_id: str, conversation_id: str | None, message: str, metadata: dict | None = None) -> str:
        run_id = f"run_{uuid.uuid4().hex}"
        db = SessionLocal()
        try:
            db.add(AgentRun(id=run_id, session_id=session_id, conversation_id=conversation_id,
                            status="queued", message=message, metadata_json=metadata or {}))
            db.commit()
        finally:
            db.close()
        self._runs[run_id] = ActiveRun(run_id=run_id)
        return run_id

    def dispatch(self, run_id: str, payload: dict[str, Any]) -> str:
        """Envía la ejecución a Celery; el worker persiste los eventos."""
        from app.workers.agent_tasks import execute_agent_task
        result = execute_agent_task.apply_async(args=[run_id, payload])
        db = SessionLocal()
        try:
            run = db.get(AgentRun, run_id)
            if run:
                run.celery_task_id = result.id
                db.commit()
        finally:
            db.close()
        return result.id

    async def start(self, run_id: str, worker) -> None:
        active = self._runs.get(run_id)
        if not active:
            raise RunNotFound(run_id)
        if active.task and not active.task.done():
            return
        active.task = asyncio.create_task(worker(active.cancel_event), name=f"agent-run:{run_id}")

    async def wait(self, run_id: str):
        active = self._runs.get(run_id)
        if active and active.task:
            return await active.task
        return None

    def is_cancelled(self, run_id: str) -> bool:
        active = self._runs.get(run_id)
        return bool(active and active.cancel_event.is_set())

    async def cancel(self, run_id: str, reason: str = "client_requested") -> bool:
        active = self._runs.get(run_id)
        db = SessionLocal()
        try:
            run = db.get(AgentRun, run_id)
            if not run:
                raise RunNotFound(run_id)
            run.cancel_requested = True
            run.status = "cancelling"
            db.commit()
        finally:
            db.close()
        if active:
            active.cancel_event.set()
            if active.task and not active.task.done():
                active.task.cancel()
        if run and run.celery_task_id:
            try:
                from app.workers.celery_app import celery_app
                celery_app.control.revoke(run.celery_task_id, terminate=False)
            except Exception:
                pass
        return True

    async def disconnect(self, run_id: str):
        active = self._runs.get(run_id)
        if not active:
            return
        if active.subscribers:
            return
        if active.disconnect_task and not active.disconnect_task.done():
            return
        async def delayed_cancel():
            try:
                from app.config import settings
                await asyncio.sleep(settings.RECONNECT_GRACE_SECONDS)
                state = self.get_run(run_id)
                if not active.subscribers and state and state.get("status") in {"queued", "running", "cancelling"}:
                    await self.cancel(run_id, reason="websocket_disconnected")
            except asyncio.CancelledError:
                pass
        active.disconnect_task = asyncio.create_task(delayed_cancel())

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        active = self._runs.get(run_id)
        if not active:
            # Completed runs can still be replayed from persistence.
            if not self.get_run(run_id):
                raise RunNotFound(run_id)
            active = ActiveRun(run_id=run_id)
            self._runs[run_id] = active
        if active.disconnect_task and not active.disconnect_task.done():
            active.disconnect_task.cancel()
        q: asyncio.Queue = asyncio.Queue(maxsize=self.MAX_QUEUE)
        active.subscribers.add(q)
        return q

    async def unsubscribe(self, run_id: str, q: asyncio.Queue):
        active = self._runs.get(run_id)
        if not active:
            return
        active.subscribers.discard(q)
        await self.disconnect(run_id)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        db = SessionLocal()
        try:
            run = db.get(AgentRun, run_id)
            if not run:
                return None
            return {"run_id": run.id, "session_id": run.session_id, "conversation_id": run.conversation_id,
                    "status": run.status, "message": run.message, "cancel_requested": run.cancel_requested, "celery_task_id": run.celery_task_id,
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None}
        finally:
            db.close()

    def events_after(self, run_id: str, after: int = 0) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = db.query(AgentEvent).filter(AgentEvent.run_id == run_id, AgentEvent.sequence > after).order_by(AgentEvent.sequence.asc()).all()
            return [{"event_id": r.id, "sequence": r.sequence, **r.payload} for r in rows]
        finally:
            db.close()

    async def persist_event(self, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        db = SessionLocal()
        try:
            last = db.query(AgentEvent.sequence).filter(AgentEvent.run_id == run_id).order_by(AgentEvent.sequence.desc()).first()
            seq = (last[0] if last else 0) + 1
            payload = dict(event)
            payload.pop("event_id", None)
            payload.pop("sequence", None)
            row = AgentEvent(run_id=run_id, sequence=seq, event_type=str(payload.get("type", "event")), payload=payload)
            db.add(row)
            db.commit()
            return {"event_id": row.id, "sequence": seq, **payload}
        finally:
            db.close()

    async def publish(self, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        enriched = await self.persist_event(run_id, event)
        active = self._runs.get(run_id)
        if active:
            for q in list(active.subscribers):
                try:
                    q.put_nowait(enriched)
                except asyncio.QueueFull:
                    # El consumidor lento puede reconectarse usando sequence.
                    pass
        return enriched

    def _mark_status(self, run_id: str, status: str):
        db = SessionLocal()
        try:
            run = db.get(AgentRun, run_id)
            if run:
                run.status = status
                run.finished_at = now() if status in {"completed", "cancelled", "failed"} else None
                db.commit()
        finally:
            db.close()

    def mark_started(self, run_id: str):
        db = SessionLocal()
        try:
            run = db.get(AgentRun, run_id)
            if run:
                run.status = "running"
                run.started_at = now()
                db.commit()
        finally:
            db.close()

    def mark_finished(self, run_id: str, status: str):
        self._mark_status(run_id, status)
        active = self._runs.get(run_id)
        if active and active.disconnect_task and not active.disconnect_task.done():
            active.disconnect_task.cancel()

    async def cleanup(self, run_id: str):
        active = self._runs.get(run_id)
        if active and active.task and not active.task.done():
            return
        if active and active.subscribers:
            return
        self._runs.pop(run_id, None)


execution_manager = ExecutionManager()
