from __future__ import annotations
import asyncio
from app.workers.celery_app import celery_app
from app.db.database import SessionLocal
from app.services.execution_manager import execution_manager

@celery_app.task(bind=True, name="agent.execute", autoretry_for=(), acks_late=True)
def execute_agent_task(self, run_id: str, payload: dict):
    return asyncio.run(_execute(run_id, payload))

async def _execute(run_id: str, payload: dict):
    from app.services.agent_service import AgentConfigurationError, AgentService
    db = SessionLocal()
    try:
        execution_manager.mark_started(run_id)
        await execution_manager.persist_event(run_id, {
            "type": "start", "run_id": run_id, "worker_task_id": getattr(execute_agent_task.request, "id", None)
        })

        async def emit(event: dict):
            await execution_manager.persist_event(run_id, {**event, "run_id": run_id})

        def cancelled() -> bool:
            state = execution_manager.get_run(run_id)
            return bool(state and state.get("cancel_requested"))

        result = await AgentService(db).run(
            payload["message"],
            session_id=payload["session_id"],
            conversation_id=payload.get("conversation_id"),
            use_rag=payload.get("use_rag", True),
            use_web=payload.get("use_web", False),
            use_google=payload.get("use_google", False),
            max_iterations=payload.get("max_iterations", 5),
            temperature=payload.get("temperature"),
            event_callback=emit,
            cancel_checker=cancelled,
        )
        await execution_manager.persist_event(run_id, {
            "type": "done", "run_id": run_id, "answer": result["answer"],
            "tools_used": result.get("tools_used", []), "sources": result.get("sources", []),
            "iterations": result.get("iterations", 0)
        })
        execution_manager.mark_finished(run_id, "completed")
        return {"run_id": run_id, "status": "completed"}
    except asyncio.CancelledError:
        execution_manager.mark_finished(run_id, "cancelled")
        await execution_manager.persist_event(run_id, {"type": "cancelled", "run_id": run_id, "reason": "execution_cancelled"})
        return {"run_id": run_id, "status": "cancelled"}
    except AgentConfigurationError as exc:
        execution_manager.mark_finished(run_id, "failed")
        await execution_manager.persist_event(run_id, {"type": "error", "run_id": run_id, "code": "LLM_CONFIGURATION", "message": str(exc)})
        raise
    except Exception as exc:
        execution_manager.mark_finished(run_id, "failed")
        await execution_manager.persist_event(run_id, {"type": "error", "run_id": run_id, "code": "AGENT_ERROR", "message": str(exc)})
        raise
    finally:
        db.close()
