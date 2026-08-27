# -*- coding: utf-8 -*-
"""任务状态 API"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(
    kb_name: str = Query(..., description="知识库名称"),
    limit: int = Query(200, ge=1, le=1000),
):
    return JSONResponse(content={"success": True, "data": job_service.list_jobs(kb_name, limit=limit)})


@router.get("/{job_id}")
async def get_job(job_id: str):
    return JSONResponse(content={"success": True, "data": job_service.get_job_detail(job_id)})


@router.post("/{job_id}/upsert")
async def upsert_job(job_id: str):
    """手动触发向量化（切片编辑后重新上传 Milvus）"""
    result = await job_service.upsert_job_to_milvus(job_id)
    return JSONResponse(content={"success": True, "message": "向量化完成", "data": result})
