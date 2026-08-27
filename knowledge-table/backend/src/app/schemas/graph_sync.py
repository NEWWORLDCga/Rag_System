"""Schemas for graph sync API."""

from typing import List, Optional

from pydantic import BaseModel


class ChunkInput(BaseModel):
    """单个 chunk 的输入（由主项目传入）."""

    chunk_id: str
    content: str
    chunk_index: int
    vector: Optional[List[float]] = None  # chunk 的语义向量（从 Milvus 复用）


class GraphSyncRequest(BaseModel):
    """主项目调用 KT 同步 chunks 到图谱的请求."""

    job_id: str
    kb_name: str
    file_name: str
    chunks: List[ChunkInput]


class GraphSyncResponse(BaseModel):
    """图谱同步响应."""

    graph_id: str
    triples_count: int
    nodes_count: int
    message: str


class GraphDeleteRequest(BaseModel):
    """删除图谱数据的请求."""

    job_id: str


class GraphDeleteResponse(BaseModel):
    """删除图谱数据的响应."""

    job_id: str
    deleted_count: int
    message: str


class TripleResponse(BaseModel):
    """图谱中单个 triple 的响应."""

    triple_id: str
    head_chunk_id: str
    head_content: str
    tail_chunk_id: str
    tail_content: str
    relation: str


class GraphQueryResponse(BaseModel):
    """图谱查询响应（返回 triples 列表）."""

    job_id: str
    kb_name: str
    triples: List[TripleResponse]
    total: int
