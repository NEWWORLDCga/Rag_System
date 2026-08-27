"""Graph API endpoints — 图谱同步和查询."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.dependencies import get_embedding_service, get_graph_milvus_service
from app.schemas.graph_sync import (
    GraphDeleteRequest,
    GraphDeleteResponse,
    GraphQueryResponse,
    GraphSyncRequest,
    GraphSyncResponse,
    TripleResponse,
)
from app.services.embedding.base import EmbeddingService
from app.services.graph_sync_service import GraphSyncService
from app.services.vector_db.graph_milvus_service import GraphMilvusService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["GraphSync"])


def get_graph_sync_service(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    graph_milvus: GraphMilvusService = Depends(get_graph_milvus_service),
    settings: Settings = Depends(get_settings),
) -> GraphSyncService:
    """依赖注入 GraphSyncService."""
    return GraphSyncService(embedding_service, graph_milvus, settings)


@router.post("/sync", response_model=GraphSyncResponse)
async def sync_graph(
    request: GraphSyncRequest,
    service: GraphSyncService = Depends(get_graph_sync_service),
) -> GraphSyncResponse:
    """同步主项目的 chunks 到知识图谱.

    主项目在文档向量化完成后调用此接口，KT 基于 chunks 语义关系生成 triples，
    并写入 Milvus 的 knowledge_graph collection。

    请求体：
        job_id: 主项目的 job_id（用于删除时匹配）
        kb_name: 知识库名称
        file_name: 文件名
        chunks: chunk 列表（chunk_id, content, chunk_index）

    响应：
        graph_id: 本次生成的图谱 ID
        triples_count: 生成的 triples 数量
        nodes_count: 图谱中的节点数量（去重后的 chunk 数）
    """
    try:
        result = await service.sync_and_save(request)
        return GraphSyncResponse(**result)
    except Exception as e:
        logger.error(f"Error syncing graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete", response_model=GraphDeleteResponse)
async def delete_graph(
    request: GraphDeleteRequest,
    graph_milvus: GraphMilvusService = Depends(get_graph_milvus_service),
) -> GraphDeleteResponse:
    """根据 job_id 删除图谱数据.

    主项目在删除带有图谱同步标签的文件时调用此接口，
    从 Milvus knowledge_graph collection 中删除对应的 triples。
    """
    try:
        result = await graph_milvus.delete_by_job(request.job_id)
        return GraphDeleteResponse(
            job_id=request.job_id,
            deleted_count=result.get("deleted_count", 0),
            message=result.get("message", "Done."),
        )
    except Exception as e:
        logger.error(f"Error deleting graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=GraphQueryResponse)
async def query_graph(
    job_id: str,
    kb_name: str,
    graph_milvus: GraphMilvusService = Depends(get_graph_milvus_service),
) -> GraphQueryResponse:
    """查询知识库对应的图谱 triples.

    主项目前端查询某个知识库的知识图谱时调用此接口，
    返回该知识库下所有文件的图谱 triples。
    """
    try:
        results = await graph_milvus.query_by_job(job_id)

        triples = [
            TripleResponse(
                triple_id=r.get("triple_id", ""),
                head_chunk_id=r.get("head_chunk_id", ""),
                head_content=r.get("head_content", ""),
                tail_chunk_id=r.get("tail_chunk_id", ""),
                tail_content=r.get("tail_content", ""),
                relation=r.get("relation", ""),
            )
            for r in results
        ]

        return GraphQueryResponse(
            job_id=job_id,
            kb_name=kb_name,
            triples=triples,
            total=len(triples),
        )
    except Exception as e:
        logger.error(f"Error querying graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))
