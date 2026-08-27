"""Graph sync service — 基于 chunks 语义关系生成 triples（不需要 Questions/Table）."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Set

from app.core.config import Settings
from app.schemas.graph_sync import ChunkInput, GraphSyncRequest
from app.services.embedding.base import EmbeddingService
from app.services.vector_db.graph_milvus_service import GraphMilvusService

logger = logging.getLogger(__name__)

# 生成 triples 的阈值配置
SIMILARITY_THRESHOLD = 0.7   # embedding cos > 0.7 认为有关联
NEIGHBOR_N = 3              # 当前 chunk 之后的 N 个 chunks 检查关系
KEYWORD_MIN_OVERLAP = 2     # 共现关键词最少重叠数


class GraphSyncService:
    """从主项目同步 chunks 并生成图谱 triples."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        graph_milvus: GraphMilvusService,
        settings: Settings,
    ) -> None:
        self.embedding_service = embedding_service
        self.graph_milvus = graph_milvus
        self.settings = settings

    def _extract_keywords(self, text: str) -> Set[str]:
        """简单关键词提取：按空格分词，去除短词和停用词."""
        stopwords = {
            "的", "了", "和", "是", "在", "有", "与", "为", "对", "上",
            "下", "中", "以", "或", "等", "于", "也", "而", "及", "将",
            "其", "被", "由", "可", "能", "要", "会", "就", "都", "不",
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "is", "are", "was", "were", "be",
        }
        words = text.lower().split()
        return {
            w.strip(".,!?;:\"'()[]{}") for w in words
            if len(w) > 2 and w.lower() not in stopwords
        }

    def _cosine_sim(self, a: List[float], b: List[float]) -> float:
        """计算两个向量的 cosine 相似度."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _generate_relation(self, head_content: str, tail_content: str) -> str:
        """根据两个 chunk 的内容生成关系名称."""
        head_lower = head_content.lower()
        tail_lower = tail_content.lower()

        # 判断关系类型
        if any(kw in head_lower for kw in ["定义", "概念", "是", "等于", "等于"]):
            return "defines"
        if any(kw in head_lower for kw in ["原因", "因为", "导致", "引起"]):
            return "causes"
        if any(kw in head_lower for kw in ["例如", "比如", "包括", "如", "例子"]):
            return "examples"
        if any(kw in tail_lower for kw in ["结论", "因此", "所以", "总结"]):
            return "concludes"
        if any(kw in head_lower for kw in ["首先", "第一", "步骤", "首先"]):
            return "followed_by"

        # 默认关系：内容连续
        return "related_to"

    async def generate_triples(
        self, request: GraphSyncRequest
    ) -> tuple[List[Dict[str, Any]], str]:
        """从 chunks 生成 triples.

        策略：
        1. 优先使用传入的 chunk 向量（从主项目复用）
        2. 如果没有传入向量，使用 embedding 服务生成
        3. 对每个 chunk，找到后续相邻的 N 个 chunks
        4. 计算语义相似度（embedding cos）> SIMILARITY_THRESHOLD → 有关联
        5. 计算共现关键词 > KEYWORD_MIN_OVERLAP → 有关联
        6. 满足任一条件则生成 triple
        """
        chunks = sorted(request.chunks, key=lambda c: c.chunk_index)
        n = len(chunks)

        if n < 2:
            logger.warning(f"Job {request.job_id}: chunks < 2 ({n}), skip graph generation")
            return [], request.job_id

        logger.info(f"Generating triples for {n} chunks, job_id={request.job_id}")

        # 检查是否有传入的向量（从主项目复用）
        has_vectors = all(c.vector and len(c.vector) > 0 for c in chunks)
        vectors_source = "main project (reused)" if has_vectors else "KT embedding service (generated)"

        if has_vectors:
            # 直接使用传入的 chunk 向量
            embeddings = [c.vector for c in chunks]
            logger.info(f"[GraphSync] Using {len(embeddings)} pre-computed chunk vectors from main project")
            logger.debug("[GraphSync] Vector sample (first 5 dims): %s",
                         [e[:5] if len(e) >= 5 else e for e in embeddings[:2]])
        else:
            # 使用 embedding 服务生成向量
            texts = [c.content for c in chunks]
            logger.warning(f"[GraphSync] No vectors from main project, generating via KT embedding service")
            embeddings = await self.embedding_service.get_embeddings(texts)

        triples: List[Dict[str, Any]] = []
        graph_id = str(uuid.uuid4())

        for i in range(n):
            head_chunk = chunks[i]
            head_emb = embeddings[i]

            # 检查后续 N 个 chunks
            for j in range(i + 1, min(i + NEIGHBOR_N + 1, n)):
                tail_chunk = chunks[j]
                tail_emb = embeddings[j]

                # 1. 语义相似度检查
                sim = self._cosine_sim(head_emb, tail_emb)
                semantic_related = sim >= SIMILARITY_THRESHOLD

                # 2. 共现关键词检查
                head_kw = self._extract_keywords(head_chunk.content)
                tail_kw = self._extract_keywords(tail_chunk.content)
                overlap = head_kw & tail_kw
                keyword_related = len(overlap) >= KEYWORD_MIN_OVERLAP

                # DEBUG 日志
                if i == 0:  # 只打印第一组的调试信息
                    logger.info(f"[DEBUG] chunk pair ({i},{j}): sim={sim:.3f}, kw_overlap={len(overlap)}, head_kw={head_kw}, tail_kw={tail_kw}")

                if semantic_related or keyword_related:
                    triple_id = f"t{uuid.uuid4().hex[:12]}"
                    relation = self._generate_relation(
                        head_chunk.content, tail_chunk.content
                    )

                    # 优先使用传入的 chunk 向量，否则设为空
                    head_vec = head_chunk.vector if head_chunk.vector else []
                    tail_vec = tail_chunk.vector if tail_chunk.vector else []

                    triples.append({
                        "triple_id": triple_id,
                        "job_id": request.job_id,
                        "kb_name": request.kb_name,
                        "file_name": request.file_name,
                        "head_chunk_id": head_chunk.chunk_id,
                        "head_content": head_chunk.content[:500],
                        "tail_chunk_id": tail_chunk.chunk_id,
                        "tail_content": tail_chunk.content[:500],
                        "relation": relation,
                        # 记录匹配原因，便于调试
                        "_match_reason": "semantic" if semantic_related else "keyword",
                        "_similarity": round(sim, 3),
                        "_keyword_overlap": len(overlap),
                        # 复用主项目的 chunk 向量（用于 triple 的语义向量）
                        "_head_vector": head_vec,
                        "_tail_vector": tail_vec,
                    })

        logger.info(
            f"Generated {len(triples)} triples for job_id={request.job_id}"
        )
        return triples, graph_id

    async def sync_and_save(self, request: GraphSyncRequest) -> Dict[str, Any]:
        """生成 triples 并写入 Milvus."""
        triples, graph_id = await self.generate_triples(request)

        if not triples:
            return {
                "graph_id": graph_id,
                "triples_count": 0,
                "nodes_count": 0,
                "message": "No related chunks found, skipped.",
            }

        # 写入 Milvus，同时生成语义向量
        await self.graph_milvus.upsert_triples(triples, self.embedding_service)

        # 统计节点数（去重 head + tail chunk_id）
        nodes: Set[str] = set()
        for t in triples:
            nodes.add(t["head_chunk_id"])
            nodes.add(t["tail_chunk_id"])

        return {
            "graph_id": graph_id,
            "triples_count": len(triples),
            "nodes_count": len(nodes),
            "message": f"Synced {len(triples)} triples, {len(nodes)} nodes.",
        }
