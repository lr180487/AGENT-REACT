from __future__ import annotations
import hashlib
import math
import httpx
from app.config import settings

class EmbeddingService:
    """OpenAI embeddings reales; hashing determinista solo como fallback local explícito."""
    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts: return []
        if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith(("sk-mock", "sk-xxx", "change-me")):
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    json={"model": settings.EMBEDDING_MODEL, "input": texts},
                )
                r.raise_for_status()
                data = r.json()["data"]
                return [x["embedding"] for x in sorted(data, key=lambda x: x["index"])]
        return [self._fallback(t) for t in texts]

    def _fallback(self, text: str) -> list[float]:
        # Fallback para SQLite/desarrollo; no se presenta como embedding semántico.
        dim = settings.EMBEDDING_DIM
        v = [0.0] * dim
        for token in text.lower().split():
            h = int(hashlib.sha256(token.encode()).hexdigest(), 16) % dim
            v[h] += 1.0
        norm = math.sqrt(sum(x*x for x in v)) or 1.0
        return [x/norm for x in v]

    @staticmethod
    def cosine(a, b):
        if not a or not b: return 0.0
        dot = sum(x*y for x,y in zip(a,b))
        na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
        return dot/(na*nb) if na and nb else 0.0
