"""API for the Knowledge Table."""

from fastapi import APIRouter

from app.api.v1.endpoints import document, graph, query
from app.api.v1 import graph_sync

api_router = APIRouter()
api_router.include_router(
    document.router, prefix="/document", tags=["document"]
)
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(query.router, prefix="/query", tags=["query"])
# 主项目调用的图谱同步接口（chunk → triples，不需要 Questions/Table）
api_router.include_router(graph_sync.router, prefix="/graph-sync", tags=["GraphSync"])
