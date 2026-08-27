# -*- coding: utf-8 -*-
"""
知识图谱检索服务（直接调用 Knowledge Table 本地 REST API）
Knowledge Table 由 WhyHow AI 开发，可通过 Docker 部署在本地（默认 http://localhost:8000），
不需要外部 API Key，数据存储在本地 Milvus / SQLite 中。

图谱检索流程：
  query_unstructured(include_chunks=True)
  → 解析 nodes/triples 中的 chunk_id
  → 批量 GET /chunks/{chunk_id} 拉正文
  → 回填 PG 原文（含图片占位符等 Milvus clean 版本没有的信息）
"""
from __future__ import annotations

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="kg_kt")


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recency_score(updated_at: Optional[str]) -> float:
    if not updated_at:
        return 0.5
    try:
        s = str(updated_at).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
        return max(0.0, min(1.0, 1.0 - min(days, 365.0) / 365.0))
    except Exception:
        return 0.5


def _unified_score(graph_score: float, updated_at: Optional[str]) -> float:
    gs = max(0.0, min(1.0, float(graph_score or 0.0)))
    rec = _recency_score(updated_at)
    return 0.65 * gs + 0.35 * rec


class KGRetrievalService:
    """
    直接调用 Knowledge Table 本地 REST API。

    API Base：来自 config.settings.knowledge_table_url
    （默认为 http://localhost:8000，可通过 KNOWLEDGE_TABLE_URL 环境变量覆盖）
    """

    def __init__(self):
        base = getattr(settings, "knowledge_table_url", None) or "http://localhost:8000"
        self._base = base.rstrip("/")
        self._timeout = 10.0  # API 请求总超时（秒）
        logger.info("[KGRetrieval] Knowledge Table API base: %s", self._base)

    # ── 公开 API ─────────────────────────────────────────────────────────────

    def query_graph(
        self,
        graph_id: str,
        query: str,
        *,
        top_k: int = 5,
        timeout: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """
        执行图谱自然语言查询，返回格式化的 chunk 列表。

        Returns:
            List[{
                "chunk_id": str,
                "content": str,
                "file_name": str,
                "chunk_index": int,
                "metadata": dict,
                "graph_score": float,
                "unified_score": float,
                "relation_types": List[str],
                "source_node_names": List[str],
                "updated_at": str,
            }]
        """
        # Step 1：query_unstructured
        logger.info("[KGRetrieval] Calling KT API | graph=%s query=%r top_k=%d",
                    graph_id, query[:80], top_k)
        try:
            result = self._query_unstructured(graph_id, query, include_chunks=True)
            logger.info("[KGRetrieval] KT API response | graph=%s nodes=%d triples=%d",
                        graph_id, len(result.get("nodes", []) or []),
                        len(result.get("triples", []) or []))
        except Exception as e:
            logger.warning("[KGRetrieval] query_unstructured 失败: %s", e)
            return []

        # Step 2：提取所有 chunk_id
        chunk_ids, relation_map = self._extract_chunk_ids(result)
        logger.info("[KGRetrieval] Extracted | graph=%s unique_chunk_ids=%d relations=%s",
                    graph_id, len(chunk_ids),
                    {k: len(v) for k, v in relation_map.items()})

        if not chunk_ids:
            logger.info(
                "[KGRetrieval] 图谱返回无 chunk_id: graph=%s query=%r",
                graph_id, query[:40]
            )
            return []

        # Step 3：批量拉 chunk 正文
        whyhow_chunks = self._batch_get_chunks(list(chunk_ids), timeout=timeout)

        # Step 4：回填 PG 原文 + 统一排序
        enriched = self._enrich_from_pg(whyhow_chunks, relation_map, top_k=top_k)

        logger.info(
            "[KGRetrieval] graph=%s query=%r → 图谱 chunk_ids=%d → 回填成功=%d",
            graph_id, query[:40], len(chunk_ids), len(enriched)
        )
        return enriched

    # ── 内部方法 ─────────────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET 请求，带超时"""
        import httpx

        url = f"{self._base}{path}"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, json: Optional[Dict] = None) -> Dict[str, Any]:
        """POST 请求，带超时"""
        import httpx

        url = f"{self._base}{path}"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, json=json)
            resp.raise_for_status()
            return resp.json()

    def _query_unstructured(
        self, graph_id: str, query: str, include_chunks: bool
    ) -> Dict[str, Any]:
        """
        POST /graphs/{graph_id}/query/unstructured

        返回结构：
        {
            "query_id": "...",
            "graph_id": "...",
            "answer": "...",
            "nodes": [{"node_id": "...", "name": "...", "chunk_ids": [...]}],
            "triples": [{"chunk_ids": [...], "relation": {"name": "..."}}],
        }
        """
        payload = {
            "query": query,
            "return_answer": True,
            "include_chunks": include_chunks,
        }
        return self._post(f"/graphs/{graph_id}/query/unstructured", json=payload)

    def _extract_chunk_ids(
        self, result: Dict[str, Any]
    ) -> tuple[set, Dict[str, set]]:
        """从 query_unstructured 结果中提取所有 chunk_id 和关系类型"""
        chunk_ids: set = set()
        relation_map: Dict[str, set] = defaultdict(set)

        # nodes[*].chunk_ids
        for node in result.get("nodes", []) or []:
            for cid in node.get("chunk_ids", []) or []:
                if cid:
                    chunk_ids.add(cid)
                    relation_map[cid].add("node_grounding")

        # triples[*].chunk_ids + relation.name
        for triple in result.get("triples", []) or []:
            rel = triple.get("relation", {}) or {}
            rel_name = rel.get("name", "related") if isinstance(rel, dict) else "related"
            for cid in triple.get("chunk_ids", []) or []:
                if cid:
                    chunk_ids.add(cid)
                    relation_map[cid].add(f"triple:{rel_name}")

        return chunk_ids, relation_map

    def _batch_get_chunks(
        self, chunk_ids: List[str], timeout: float
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """并发 GET /chunks/{chunk_id}，超时降级为空"""
        if not chunk_ids:
            return {}

        def _get_one(cid: str) -> tuple[str, Optional[Dict[str, Any]]]:
            try:
                data = self._get(f"/chunks/{cid}")
                content = data.get("content", "") or ""
                if isinstance(content, dict):
                    content = content.get("text", "") or str(content)

                meta = data.get("metadata") or {}
                idx = meta.get("index") if isinstance(meta, dict) else None

                return cid, {
                    "content": str(content).strip(),
                    "document_id": data.get("document_id"),
                    "chunk_index": idx,
                    "metadata": meta if isinstance(meta, dict) else {},
                    "updated_at": _now_ts(),
                }
            except Exception as e:
                logger.debug("[KGRetrieval] GET /chunks/%s 失败: %s", cid, e)
                return cid, None

        results: Dict[str, Optional[Dict[str, Any]]] = {}
        try:
            futs = [_executor.submit(_get_one, cid) for cid in chunk_ids]
            for fut in futs:
                try:
                    cid, data = fut.result(timeout=timeout)
                    if data is not None:
                        results[cid] = data
                except FuturesTimeout:
                    break
        except Exception as e:
            logger.warning("[KGRetrieval] 批量 get_chunks 异常: %s", e)

        return {cid: d for cid, d in results.items() if d is not None}

    def _enrich_from_pg(
        self,
        whyhow_chunks: Dict[str, Optional[Dict[str, Any]]],
        relation_map: Dict[str, set],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """回填 PG 原文，然后用 unified_score 排序截断"""
        if not whyhow_chunks:
            return []

        try:
            from app.db import get_chunk_repository
            chunk_repo = get_chunk_repository()
            pg_rows = chunk_repo.get_by_ids_with_file_names(list(whyhow_chunks.keys()))
            pg_map = {r["chunk_id"]: r for r in pg_rows}
        except Exception as e:
            logger.warning("[KGRetrieval] PG 回填失败，使用 API 正文: %s", e)
            pg_map = {}

        scored: List[Dict[str, Any]] = []
        for cid, wc in whyhow_chunks.items():
            if wc is None:
                continue
            pg = pg_map.get(cid, {})

            # 优先用 PG 原文（保留图片占位符等），否则降级到 KT 正文
            content = pg.get("current_content") or pg.get("content") or wc.get("content") or ""
            file_name = pg.get("file_name") or wc.get("metadata", {}).get("file_name", "")
            chunk_index = (
                pg.get("chunk_index")
                if pg.get("chunk_index") is not None
                else wc.get("chunk_index")
            )
            updated_at = pg.get("updated_at") or wc.get("updated_at", "")
            meta = pg.get("metadata") or wc.get("metadata") or {}
            if file_name and "file_name" not in meta:
                meta = {**meta, "file_name": file_name}

            gs = 0.8  # KT 返回的节点/triple 均视为高置信度
            unified = _unified_score(gs, str(updated_at) if updated_at else None)

            scored.append({
                "chunk_id": cid,
                "content": content,
                "file_name": file_name,
                "chunk_index": chunk_index,
                "metadata": meta,
                "graph_score": gs,
                "unified_score": unified,
                "relation_types": sorted(relation_map.get(cid, set())),
                "source_node_names": [],
                "updated_at": str(updated_at) if updated_at else "",
            })

        scored.sort(key=lambda x: float(x.get("unified_score") or 0.0), reverse=True)
        return scored[:max(1, top_k)]


_instance: Optional[KGRetrievalService] = None


def get_kg_retrieval_service() -> KGRetrievalService:
    global _instance
    if _instance is None:
        _instance = KGRetrievalService()
    return _instance
