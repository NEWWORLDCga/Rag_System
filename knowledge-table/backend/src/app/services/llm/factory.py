"""Factory for creating language model completion services."""

import logging
from typing import Optional

from app.core.config import Settings
from app.services.llm.base import CompletionService
from app.services.llm.openai_llm_service import OpenAICompletionService

logger = logging.getLogger(__name__)


class CompletionServiceFactory:
    """Factory for creating completion services."""

    @staticmethod
    def create_service(settings: Settings) -> Optional[CompletionService]:
        """Create a completion service (provider 固定为 openai，base_url 指向百炼)."""
        logger.info(f"Creating completion service (provider: {settings.llm_provider}, base_url: {settings.openai_base_url})")
        if settings.llm_provider == "openai":
            return OpenAICompletionService(settings)
        return None