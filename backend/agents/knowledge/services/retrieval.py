# -*- coding: utf-8 -*-
"""
Retrieval Service - Milvus 混合检索
"""
from typing import List, Optional
import logging
from app.services.milvus_service import get_milvus_service

logger = logging.getLogger(__name__)


class RetrievalService:

    def vector_search(
        self,
        query: str,
        top_k: int = 10,
        filter_expr: Optional[str] = None,
        collection: Optional[str] = None,
        ranker: str = "RRF",
        rrf_k: int = 60,
        hybrid_alpha: float = 0.5,
    ) -> List[dict]:
        """Dense + BM25 双路混合检索（主要入口）"""
        if not collection:
            logger.warning("[Retrieval] collection 未指定，跳过检索")
            return []
        return get_milvus_service().hybrid_search(
            collection_name=collection,
            query=query,
            top_k=top_k,
            filter_expr=filter_expr,
            ranker=ranker,
            rrf_k=rrf_k,
            hybrid_alpha=hybrid_alpha,
        )

    def keyword_search(
        self,
        query: str,
        top_k: int = 10,
        filter_expr: Optional[str] = None,
        collection: Optional[str] = None,
        keyword_filter: Optional[str] = None,
        ranker: str = "RRF",
        rrf_k: int = 60,
        hybrid_alpha: float = 0.5,
    ) -> List[dict]:
        """TEXT_MATCH 倒排索引预过滤 + Dense + BM25 双路混合检索。"""
        if not collection:
            logger.warning("[Retrieval] collection 未指定，跳过检索")
            return []
        kw = keyword_filter or query
        return get_milvus_service().hybrid_search(
            collection_name=collection,
            query=query,
            top_k=top_k,
            filter_expr=filter_expr,
            keyword_filter=kw,
            ranker=ranker,
            rrf_k=rrf_k,
            hybrid_alpha=hybrid_alpha,
        )

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        filter_expr: Optional[str] = None,
        collection: Optional[str] = None,
        group_by_field: Optional[str] = None,
        group_size: int = 1,
        strict_group_size: bool = False,
        ranker: str = "RRF",
        rrf_k: int = 60,
        hybrid_alpha: float = 0.5,
    ) -> List[dict]:
        """纯双路混合检索，支持分组搜索"""
        if not collection:
            logger.warning("[Retrieval] collection 未指定，跳过检索")
            return []
        return get_milvus_service().hybrid_search(
            collection_name=collection,
            query=query,
            top_k=top_k,
            filter_expr=filter_expr,
            group_by_field=group_by_field,
            group_size=group_size,
            strict_group_size=strict_group_size,
            ranker=ranker,
            rrf_k=rrf_k,
            hybrid_alpha=hybrid_alpha,
        )


_retrieval_service = None


def get_retrieval_service() -> RetrievalService:
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service
