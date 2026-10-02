from __future__ import annotations

import json
import uuid
from typing import Any, Awaitable, Callable, Optional
import asyncio

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.db.repositories.chat_repository import ChatRepository
from app.db.repositories.message_repository import MessageRepository
from app.db.repositories.memory_repository import MemoryRepository
from app.services.analyzer_service import AnalyzerService
from app.services.processor_service import ProcessorService
from app.tools.google_search import google_search


SYSTEM_PROMPT = """Eres un agente ReAct para una aplicación RAG.

Tu trabajo es resolver la solicitud usando herramientas cuando aporten información verificable.
No inventes resultados de herramientas. Puedes hacer varias iteraciones: pensar qué necesitas,
llamar una herramienta, revisar su resultado y llamar otra si hace falta. Cuando tengas suficiente
información, responde directamente al usuario.

Reglas:
- Usa rag para preguntas que puedan resolverse con documentos indexados.
- Usa documents para localizar documentos por nombre o estado.
- Usa web_search solo si está habilitado y necesitas información externa/actualizada.
- Usa google_search cuando Google esté habilitado y necesites resultados públicos externos o actualizados.
- Usa memory para recuperar contexto de la conversación actual.
- No llames herramientas innecesariamente.
- Distingue claramente hechos encontrados en herramientas de inferencias.
- Si una herramienta no está disponible, continúa con otra fuente o explica la limitación.
- La respuesta final debe ser útil, concisa y en el idioma del usuario.
"""


class AgentConfigurationError(RuntimeError):
    pass


class AgentService:
    """LLM tool-calling loop: implementación ReAct moderna basada en tool calls.

    El LLM decide iterativamente qué herramienta ejecutar. El Analyzer sigue disponible
    como señal auxiliar para mejorar el contexto, pero no ejecuta el plan por sí mismo.
    """

    def __init__(self, db: Session):
        self.db = db
        self.processor = ProcessorService(db)
        self.messages = MessageRepository(db)
        self.chats = ChatRepository(db)
        self.memory = MemoryRepository(db)

    def _provider_config(self) -> tuple[str, str, str]:
        provider = (settings.LLM_PROVIDER or "openai").lower()
        model = settings.LLM_MODEL
        api_key = None
        base_url = settings.LLM_BASE_URL

        if provider == "openai":
            api_key = settings.OPENAI_API_KEY
            base_url = base_url or "https://api.openai.com/v1"
        elif provider == "groq":
            api_key = settings.GROQ_API_KEY
            base_url = base_url or "https://api.groq.com/openai/v1"
        elif provider in {"custom", "openai-compatible", "ollama"}:
            api_key = settings.OPENAI_API_KEY or "ollama"
            base_url = base_url or "http://localhost:11434/v1"
        else:
            raise AgentConfigurationError(
                f"Proveedor '{provider}' no implementa todavía el protocolo OpenAI-compatible "
                "en AgentService. Configura openai, groq, ollama o custom."
            )

        if not api_key:
            raise AgentConfigurationError(
                f"No hay credencial configurada para el proveedor '{provider}'. "
                "Configura la variable API correspondiente."
            )
        return api_key, base_url.rstrip("/"), model

    def _tool_definitions(self, *, use_rag: bool, use_web: bool, use_google: bool, chat_id: Optional[str]) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        if use_rag:
            tools.append({
                "type": "function",
                "function": {
                    "name": "rag",
                    "description": "Busca semánticamente en los documentos indexados.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            })
        tools.append({
            "type": "function",
            "function": {
                "name": "documents",
                "description": "Localiza documentos disponibles por nombre o texto relacionado.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        })
        tools.append({
            "type": "function",
            "function": {
                "name": "memory",
                "description": "Recupera memoria e historial reciente de la conversación actual.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        })
        if use_web:
            tools.append({
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Busca información externa mediante Tavily.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            })
        if use_google:
            tools.append({
                "type": "function",
                "function": {
                    "name": "google_search",
                    "description": "Busca información pública en Google mediante Programmable Search. Úsala para información externa o actualizada cuando Google esté habilitado.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "num_results": {"type": "integer", "minimum": 1, "maximum": 10},
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            })
        return tools

    async def _call_llm(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], temperature: Optional[float] = None) -> dict[str, Any]:
        api_key, base_url, model = self._provider_config()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "max_tokens": settings.LLM_MAX_TOKENS,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise AgentConfigurationError(f"No se pudo conectar al LLM en {base_url}: {exc}") from exc
        if response.status_code >= 400:
            detail = response.text[:1000]
            raise AgentConfigurationError(f"LLM HTTP {response.status_code}: {detail}")
        return response.json()

    async def _stream_final_answer(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: Optional[float],
        event_callback: Optional[Callable[[dict[str, Any]], Awaitable[None]]],
    ) -> str:
        """Genera únicamente la respuesta final usando SSE/stream=true.

        Se utiliza después de la fase de tool-calling para que los deltas visibles
        al usuario nunca sean fragmentos de una iteración interna del agente.
        """
        api_key, base_url, model = self._provider_config()
        stream_messages = list(messages)
        stream_messages.append({
            "role": "system",
            "content": (
                "Genera ahora la respuesta final para el usuario. No describas tu proceso interno, "
                "no menciones chain-of-thought y no llames herramientas. Responde directamente "
                "con la información disponible en la conversación y las herramientas."
            ),
        })
        payload: dict[str, Any] = {
            "model": model,
            "messages": stream_messages,
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "text/event-stream"}
        answer_parts: list[str] = []

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("POST", f"{base_url}/chat/completions", headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        detail = (await response.aread()).decode("utf-8", errors="replace")[:1000]
                        raise AgentConfigurationError(f"LLM HTTP {response.status_code}: {detail}")
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = (choices[0].get("delta") or {}).get("content")
                        if not delta:
                            continue
                        answer_parts.append(delta)
                        await self._emit(event_callback, {"type": "delta", "delta": delta})
        except httpx.HTTPError as exc:
            raise AgentConfigurationError(f"No se pudo conectar al stream LLM en {base_url}: {exc}") from exc

        answer = "".join(answer_parts).strip()
        if not answer:
            raise AgentConfigurationError("El LLM no produjo contenido en el stream final.")
        return answer

    async def _run_tool(self, name: str, arguments: dict[str, Any], *, chat_id: Optional[str]) -> dict[str, Any]:
        if name == "rag":
            return await self.processor.rag(
                arguments.get("query", ""),
                chat_id=chat_id,
                top_k=int(arguments.get("top_k", 5)),
            )
        if name == "documents":
            return await self.processor.documents(arguments.get("query", ""))
        if name == "memory":
            return self._memory(arguments.get("query", ""), chat_id)
        if name == "web_search":
            return await self.processor.web_search(arguments.get("query", ""))
        if name == "google_search":
            return await google_search(arguments.get("query", ""), num_results=int(arguments.get("num_results", 5)))
        return {"tool": name, "available": False, "error": "Herramienta no permitida"}

    def _memory(self, query: str, chat_id: Optional[str]) -> dict[str, Any]:
        if not chat_id:
            return {"tool": "memory", "available": False, "error": "No hay conversation_id"}
        memory = self.memory.get_by_chat(chat_id)
        _, rows = self.messages.list(chat_id, limit=20)
        return {
            "tool": "memory",
            "query": query,
            "summary": memory.summary if memory else None,
            "messages": [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None}
                for m in rows
            ],
        }

    async def _emit(
        self,
        callback: Optional[Callable[[dict[str, Any]], Awaitable[None]]],
        event: dict[str, Any],
    ) -> None:
        if callback is not None:
            await callback(event)

    async def run(
        self,
        message: str,
        *,
        session_id: str,
        conversation_id: Optional[str] = None,
        use_rag: bool = True,
        use_web: bool = False,
        max_iterations: int = 5,
        temperature: Optional[float] = None,
        event_callback: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
        cancel_event: Optional[asyncio.Event] = None,
        cancel_checker: Optional[Callable[[], bool]] = None,
        use_google: bool = False,
    ) -> dict[str, Any]:
        analyzer = AnalyzerService().analyze(message, chat_id=conversation_id)
        tools = self._tool_definitions(use_rag=use_rag, use_web=use_web, use_google=use_google, chat_id=conversation_id)

        history: list[dict[str, Any]] = []
        if conversation_id:
            _, previous = self.messages.list(conversation_id, limit=12)
            history = [{"role": m.role, "content": m.content} for m in previous if m.role in {"user", "assistant"}]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "system",
                "content": "Señales auxiliares del Analyzer (no son instrucciones obligatorias): "
                           + json.dumps(analyzer, ensure_ascii=False),
            },
            *history,
            {"role": "user", "content": message},
        ]

        used_tools: list[str] = []
        tool_trace: list[dict[str, Any]] = []
        iterations = 0

        await self._emit(event_callback, {"type": "start", "session_id": session_id, "conversation_id": conversation_id, "max_iterations": max_iterations})
        await self._emit(event_callback, {"type": "thinking", "status": "analyzing_request", "iteration": 0})

        while iterations < max_iterations:
            if (cancel_event and cancel_event.is_set()) or (cancel_checker and cancel_checker()):
                raise asyncio.CancelledError
            iterations += 1
            await self._emit(event_callback, {"type": "thinking", "status": "deciding_next_action", "iteration": iterations})
            data = await self._call_llm(messages, tools, temperature=temperature)
            choice = (data.get("choices") or [{}])[0]
            assistant = choice.get("message") or {}
            tool_calls = assistant.get("tool_calls") or []
            content = assistant.get("content") or ""

            assistant_message: dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            messages.append(assistant_message)

            if not tool_calls:
                # La primera respuesta sin tools se usa como señal de finalización;
                # la respuesta visible se genera en un segundo request con streaming real.
                await self._emit(event_callback, {"type": "thinking", "status": "streaming_final", "iteration": iterations})
                if (cancel_event and cancel_event.is_set()) or (cancel_checker and cancel_checker()):
                    raise asyncio.CancelledError
                answer = await self._stream_final_answer(
                    messages,
                    temperature=temperature,
                    event_callback=event_callback,
                )
                if conversation_id:
                    self._persist(conversation_id, message, answer)
                await self._emit(event_callback, {"type": "final", "answer": answer, "iterations": iterations, "tools_used": list(dict.fromkeys(used_tools))})
                return {
                    "answer": answer,
                    "tools_used": list(dict.fromkeys(used_tools)),
                    "sources": self._sources_from_trace(tool_trace),
                    "tool_trace": tool_trace,
                    "iterations": iterations,
                    "analyzer": analyzer,
                    "model": settings.LLM_MODEL,
                    "provider": settings.LLM_PROVIDER,
                    "session_id": session_id,
                }

            for call in tool_calls:
                function = call.get("function") or {}
                name = function.get("name", "")
                raw_args = function.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}

                await self._emit(event_callback, {"type": "tool_call", "iteration": iterations, "tool": name, "arguments": args})
                if (cancel_event and cancel_event.is_set()) or (cancel_checker and cancel_checker()):
                    raise asyncio.CancelledError
                result = await self._run_tool(name, args, chat_id=conversation_id)
                used_tools.append(name)
                await self._emit(event_callback, {"type": "tool_result", "iteration": iterations, "tool": name, "result": self._safe_event_result(result)})
                tool_trace.append({"iteration": iterations, "tool": name, "arguments": args, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", str(uuid.uuid4())),
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

        # Última chamada sem tools para forzar una síntesis después del límite de iteraciones.
        messages.append({
            "role": "system",
            "content": "Has alcanzado el máximo de iteraciones. Sintetiza ahora con la evidencia disponible; no llames más herramientas.",
        })
        await self._emit(event_callback, {"type": "thinking", "status": "streaming_final", "iteration": iterations, "forced_synthesis": True})
        if (cancel_event and cancel_event.is_set()) or (cancel_checker and cancel_checker()):
            raise asyncio.CancelledError
        final_message = await self._stream_final_answer(
            messages,
            temperature=temperature,
            event_callback=event_callback,
        )
        if conversation_id:
            self._persist(conversation_id, message, final_message)
        await self._emit(event_callback, {"type": "final", "answer": final_message, "iterations": iterations, "tools_used": list(dict.fromkeys(used_tools)), "forced_synthesis": True})
        return {
            "answer": final_message,
            "tools_used": list(dict.fromkeys(used_tools)),
            "sources": self._sources_from_trace(tool_trace),
            "tool_trace": tool_trace,
            "iterations": iterations,
            "analyzer": analyzer,
            "model": settings.LLM_MODEL,
            "provider": settings.LLM_PROVIDER,
            "session_id": session_id,
        }

    def _safe_event_result(self, result: Any, max_chars: int = 5000) -> Any:
        """Reduce payloads sent over WS; never expose hidden LLM reasoning."""
        try:
            text = json.dumps(result, ensure_ascii=False, default=str)
            if len(text) > max_chars:
                return {"truncated": True, "preview": text[:max_chars]}
            return result
        except Exception:
            return {"truncated": True, "preview": str(result)[:max_chars]}

    def _sources_from_trace(self, trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for item in trace:
            result = item.get("result") or {}
            tool = item.get("tool")
            if tool in {"web_search", "google_search"}:
                for hit in result.get("results", [])[:10]:
                    if hit.get("url"):
                        sources.append({"titulo": hit.get("title", hit.get("url", "")), "url": hit["url"], "tipo": tool})
            elif tool == "rag":
                for chunk in result.get("chunks", [])[:10]:
                    sources.append({"titulo": f"Documento {chunk.get('document_id', '')}", "url": f"doc://{chunk.get('document_id', '')}", "tipo": "rag", "score": chunk.get("score")})
        return sources[:10]

    def _persist(self, conversation_id: str, user_message: str, assistant_message: str) -> None:
        chat = self.chats.get(conversation_id)
        if not chat:
            return
        # El frontend puede persistir el mensaje de usuario antes de abrir el stream.
        # Evitamos duplicarlo si ya es el último mensaje de la conversación.
        _, recent = self.messages.list(conversation_id, limit=1)
        last = recent[-1] if recent else None
        if not last or last.role != "user" or last.content != user_message:
            self.messages.create(conversation_id, "user", user_message)
        self.messages.create(conversation_id, "assistant", assistant_message)
