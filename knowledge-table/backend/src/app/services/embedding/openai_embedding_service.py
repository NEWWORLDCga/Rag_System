"""Embedding service implementation — OpenAI SDK，base_url 指向百炼（与主项目一致）."""
from __future__ import annotations

import logging
from typing import List

from openai import OpenAI

from app.core.config import Settings
from app.services.embedding.base import EmbeddingService

logger = logging.getLogger(__name__)


class OpenAIEmbeddingService(EmbeddingService):
    """百炼 OpenAI 兼容端点下的 embedding 服务."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = settings.embedding_model
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required but not set")

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量生成向量（text-embedding-v3 单次最多 10 条）."""
        if not texts:
            return []

        all_vectors: List[List[float]] = []
        batch_size = 10

        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            resp = self.client.embeddings.create(
                input=batch,
                model=self.model,
                dimensions=self.settings.dimensions,
            )
            all_vectors.extend([item.embedding for item in resp.data])

        return all_vectors