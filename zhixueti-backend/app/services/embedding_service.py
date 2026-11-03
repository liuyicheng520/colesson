"""Text embedding for vector knowledge-base retrieval."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from functools import lru_cache

import os

import httpx

# fastembed 首次加载会联网下载模型；离线环境下每次失败重试约 40-50s。
# 这里在导入前写入进程环境，确保失败快速返回（仍会自动降级为 hash 向量）。
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

logger = logging.getLogger(__name__)
_HASH_DIM = 384


def _hash_embed(text: str, dim: int = _HASH_DIM) -> list[float]:
    vec = [0.0] * dim
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class EmbeddingService:
    def __init__(self) -> None:
        from app.core.config import get_settings

        self.settings = get_settings()
        self._fastembed = None
        self._use_fastembed: bool | None = None

    @property
    def is_fallback(self) -> bool:
        """是否在用 hash 兜底向量（非语义模型）。hash 向量的余弦分数天然偏低，
        检索阈值需要相应下调，否则会把正确结果全部过滤掉。"""
        return self._use_fastembed is False

    def _try_fastembed_model(self):
        if self._use_fastembed is False:
            return None
        if self._fastembed is not None:
            return self._fastembed
        try:
            from fastembed import TextEmbedding

            model_name = self.settings.kb_embedding_model or "BAAI/bge-small-zh-v1.5"
            self._fastembed = TextEmbedding(model_name=model_name)
            self._use_fastembed = True
            return self._fastembed
        except Exception as exc:
            logger.warning("fastembed unavailable, fallback to hash embedding: %s", exc)
            self._use_fastembed = False
            return None

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        provider = (self.settings.kb_embedding_provider or "fastembed").lower()
        if provider == "qwen" and self.settings.qwen_api_key:
            try:
                return await self._embed_qwen(texts)
            except Exception as exc:
                logger.warning("qwen embedding failed, fallback to hash: %s", exc)
        model = self._try_fastembed_model()
        if model is not None:
            try:
                return [list(v) for v in model.embed(texts)]
            except Exception as exc:
                logger.warning("fastembed runtime failed, fallback to hash: %s", exc)
        return [_hash_embed(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        vecs = await self.embed_texts([text])
        return vecs[0] if vecs else []

    async def _embed_qwen(self, texts: list[str]) -> list[list[float]]:
        url = f"{self.settings.qwen_base_url.rstrip('/')}/embeddings"
        headers = {"Authorization": f"Bearer {self.settings.qwen_api_key}"}
        model = self.settings.kb_embedding_model or "text-embedding-v3"
        out: list[list[float]] = []
        batch = 16
        async with httpx.AsyncClient(timeout=60) as client:
            for i in range(0, len(texts), batch):
                part = texts[i : i + batch]
                resp = await client.post(
                    url,
                    headers=headers,
                    json={"model": model, "input": part},
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                data.sort(key=lambda x: x["index"])
                out.extend([item["embedding"] for item in data])
        return out


_embedding_service_singleton: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """进程内单例：模型探测结果（含降级状态）必须跨请求复用。"""
    global _embedding_service_singleton
    if _embedding_service_singleton is None:
        _embedding_service_singleton = EmbeddingService()
    return _embedding_service_singleton
