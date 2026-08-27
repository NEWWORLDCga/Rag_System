# -*- coding: utf-8 -*-
"""系统配置查询 API"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services.milvus_service import get_milvus_service

router = APIRouter(prefix="/config", tags=["admin-config"])


@router.get("")
async def get_config():
    milvus_svc = get_milvus_service()
    collections = []
    try:
        collections = milvus_svc.list_collections()
    except Exception as e:
        pass

    return JSONResponse(content={
        "success": True,
        "data": {
            "milvus": {
                "host": settings.milvus_host,
                "port": settings.milvus_port,
                "collections": collections,
            },
            "postgres": {
                "host": settings.pg_host,
                "port": settings.pg_port,
                "db": settings.pg_db,
            },
            "embedding": {
                "model": settings.embedding_model,
                "dimension": settings.embedding_dimension,
            },
        },
    })
