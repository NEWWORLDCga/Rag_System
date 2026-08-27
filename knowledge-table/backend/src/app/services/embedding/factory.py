"""Factory for creating embedding services."""

import logging
from typing import Optional

from app.core.config import Settings
from app.services.embedding.base import EmbeddingService
from app.services.embedding.openai_embedding_service import OpenAIEmbeddingService

logger = logging.getLogger(__name__)


class EmbeddingServiceFactory:
    """Factory for creating embedding services."""

    @staticmethod
    def create_service(settings: Settings) -> Optional[EmbeddingService]:
        """Create an embedding service (provider 固定为 openai，base_url 指向百炼)."""
        logger.info(f"Creating embedding service (provider: {settings.embedding_provider}, base_url: {settings.openai_base_url})")
        if settings.embedding_provider == "openai":
            return OpenAIEmbeddingService(settings)
        return None