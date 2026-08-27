"""LLM completion service — OpenAI SDK，base_url 指向百炼（与主项目一致）.

DashScope 的 qwen-plus 支持：
- response_format={"type": "json_object"}  → 强制 JSON 输出
- 不支持 OpenAI 的 beta.chat.completions.parse，改用 json_object + 解析
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional, Type

from openai import OpenAI
from pydantic import BaseModel

from app.core.config import Settings
from app.services.llm.base import CompletionService

logger = logging.getLogger(__name__)


def _choose_response_format(model_cls: Type[BaseModel]) -> dict:
    """根据响应 model 选择 DashScope 的 response_format."""
    name = model_cls.__name__
    # 百炼 qwen 支持 json_object 模式
    if name in ("KeywordsResponseModel", "SubQueriesResponseModel", "SchemaResponseModel"):
        return {"type": "json_object"}
    # 其他类型用 text（稍后解析）
    return {"type": "text"}


class OpenAICompletionService(CompletionService):
    """百炼 OpenAI 兼容端点下的 LLM 服务."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = settings.llm_model
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required but not set")

    async def generate_completion(
        self, prompt: str, response_model: Type[BaseModel]
    ) -> Optional[BaseModel]:
        """调用百炼，强制 JSON 模式，解析到 Pydantic model."""
        rf = _choose_response_format(response_model)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format=rf,
            )
        except Exception as e:
            logger.error(f"百炼 API 调用异常: {e}")
            return None

        raw = resp.choices[0].message.content or ""

        # 解析 JSON（可能含 markdown 代码块）
        try:
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(
                    lines[1:-1] if len(lines) > 1 and lines[-1].strip() == "```"
                    else lines[1:]
                )
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}\n原始响应: {raw[:300]}")
            return None

        try:
            return response_model(**parsed)
        except Exception as e:
            logger.error(f"Pydantic 验证失败: {e}\n数据: {parsed}")
            return None

    async def decompose_query(self, query: str) -> dict[str, Any]:
        """将复杂查询分解为多个子查询."""
        return {"sub_queries": [query]}