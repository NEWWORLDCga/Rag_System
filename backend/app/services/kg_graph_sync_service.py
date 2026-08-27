# -*- coding: utf-8 -*-
"""
知识图谱同步服务
调用 Knowledge Table 的 REST API，将主项目的 chunks 同步到知识图谱。

KT 端点（Docker 部署在 localhost:8001）：
  POST /api/v1/graph-sync/sync   - 同步 chunks → triples
  DELETE /api/v1/graph-sync/delete - 根据 job_id 删除图谱数据
  POST /api/v1/graph-sync/query - 查询知识库图谱
"""
import logging
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

# KT 图谱 API 地址（Docker 部署在 8001）
KT_GRAPH_BASE_URL = "http://localhost:8001/api/v1/graph-sync"


class KGGraphSyncService:
    """主项目调用 Knowledge Table 图谱 API 的客户端."""

    def __init__(self, base_url: str = KT_GRAPH_BASE_URL, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout)

    async def sync_chunks_to_graph(
        self,
        job_id: str,
        kb_name: str,
        file_name: str,
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        将 chunks 同步到知识图谱。

        调用 KT POST /api/v1/graph-sync/sync
        KT 基于 chunks 语义关系生成 triples，写入 Milvus knowledge_graph collection。

        Args:
            job_id: 主项目的 job_id（用于后续删除匹配）
            kb_name: 知识库名称
            file_name: 文件名
            chunks: chunk 列表，每个元素包含 chunk_id, content, chunk_index

        Returns:
            {"graph_id": "...", "triples_count": N, "nodes_count": M, "message": "..."}
        """
        payload = {
            "job_id": job_id,
            "kb_name": kb_name,
            "file_name": file_name,
            "chunks": [
                {
                    "chunk_id": c["chunk_id"],
                    "content": c["content"],
                    "chunk_index": c["chunk_index"],
                    "vector": c.get("vector", []),
                }
                for c in chunks
            ],
        }

        logger.info(f"[KGGraphSync] syncing {len(chunks)} chunks to graph, job_id={job_id}, kb_name={kb_name}")

        try:
            with self._client() as client:
                resp = client.post(f"{self.base_url}/sync", json=payload)
                resp.raise_for_status()
                result = resp.json()
                logger.info(
                    f"[KGGraphSync] synced job_id={job_id} → "
                    f"triples={result.get('triples_count', 0)}, "
                    f"nodes={result.get('nodes_count', 0)}"
                )
                return result
        except httpx.HTTPStatusError as e:
            logger.error(f"[KGGraphSync] HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[KGGraphSync] sync failed: {e}")
            raise

    async def delete_graph_by_job(self, job_id: str) -> Dict[str, Any]:
        """
        根据 job_id 删除图谱数据。

        调用 KT DELETE /api/v1/graph-sync/delete

        Args:
            job_id: 主项目的 job_id

        Returns:
            {"job_id": "...", "deleted_count": N, "message": "..."}
        """
        payload = {"job_id": job_id}

        try:
            with self._client() as client:
                resp = client.request("DELETE", f"{self.base_url}/delete", json=payload)
                resp.raise_for_status()
                result = resp.json()
                logger.info(
                    f"[KGGraphSync] deleted job_id={job_id}, "
                    f"count={result.get('deleted_count', 0)}"
                )
                return result
        except httpx.HTTPStatusError as e:
            logger.error(f"[KGGraphSync] HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[KGGraphSync] delete failed: {e}")
            raise

    async def query_graph(self, job_id: str, kb_name: str) -> Dict[str, Any]:
        """
        查询知识库的图谱 triples。

        调用 KT POST /api/v1/graph-sync/query（使用 query 参数）

        Returns:
            {"job_id": "...", "kb_name": "...", "triples": [...], "total": N}
        """
        try:
            with self._client() as client:
                resp = client.post(
                    f"{self.base_url}/query",
                    params={"job_id": job_id, "kb_name": kb_name},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"[KGGraphSync] HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[KGGraphSync] query failed: {e}")
            raise


# 单例
_instance: KGGraphSyncService | None = None


def get_kg_graph_sync_service() -> KGGraphSyncService:
    global _instance
    if _instance is None:
        _instance = KGGraphSyncService()
    return _instance
