# -*- coding: utf-8 -*-
"""
判断当前问题是否需要更深的图谱遍历（更多跳 / 更高关系配额由 graph_retrieve 使用）
"""
import logging
from datetime import datetime

from dashscope import Generation

from ..state import KnowledgeAgentState
from app.core.config import settings
from app.core.prompts import KNOWLEDGE_KG_DEEP_ROUTE_SYSTEM

logger = logging.getLogger(__name__)


def kg_query_route(state: KnowledgeAgentState) -> dict:
    start = datetime.now()
    cfg = state.get("config")
    if not cfg or not getattr(cfg, "kg_enabled", True):
        return {
            "kg_deep_traversal": False,
            "processing_log": [{"stage": "kg_query_route", "skipped": True, "reason": "kg_disabled"}],
        }

    query = state.get("rewritten_query") or state.get("query") or ""
    if not (query or "").strip():
        return {"kg_deep_traversal": False, "processing_log": [{"stage": "kg_query_route", "skipped": True}]}

    try:
        messages = [
            {"role": "system", "content": KNOWLEDGE_KG_DEEP_ROUTE_SYSTEM},
            {"role": "user", "content": f"用户问题：{query}\n\n只输出 yes 或 no："},
        ]
        response = Generation.call(
            api_key=settings.dashscope_api_key,
            model=settings.llm_clean_model,
            messages=messages,
            result_format="message",
        )
        text = ""
        if response.status_code == 200:
            msg = response.output.choices[0].message
            text = (msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")) or ""
        text = (text or "").strip().lower()
        deep = text.startswith("y") or "yes" in text[:8] or "是" in text[:4]
        ms = (datetime.now() - start).total_seconds() * 1000
        logger.info("[KgQueryRoute] deep=%s raw=%r (%.0fms)", deep, text[:80], ms)
        return {
            "kg_deep_traversal": deep,
            "processing_log": [{"stage": "kg_query_route", "duration_ms": ms, "kg_deep_traversal": deep}],
        }
    except Exception as e:
        logger.warning("[KgQueryRoute] 失败，默认浅层: %s", e)
        return {
            "kg_deep_traversal": False,
            "all_warnings": [f"kg_query_route_failed:{e}"],
        }
