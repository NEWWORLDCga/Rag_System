# -*- coding: utf-8 -*-
"""文件列表 API"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services import file_service

router = APIRouter(prefix="/files", tags=["files"])


class DeleteFileRequest(BaseModel):
    file_id: str


class BatchDeleteFilesRequest(BaseModel):
    file_ids: list[str]
    kb_name: str


@router.get("")
async def list_files(
    kb_name: str = Query(..., description="知识库名称"),
    limit: int = Query(default=200, ge=1, le=2000),
):
    result = file_service.list_files(kb_name=kb_name, limit=limit)
    return JSONResponse(content={"success": True, "data": result})


@router.delete("")
async def delete_file(req: DeleteFileRequest):
    file_name = file_service.delete_file(req.file_id)
    return JSONResponse(content={"success": True, "message": f"文件「{file_name}」已删除"})


@router.post("/batch-delete")
async def batch_delete_files(req: BatchDeleteFilesRequest):
    result = file_service.batch_delete_files(req.file_ids, req.kb_name)
    ok = len(result["deleted"])
    fail = len(result["failed"])
    return JSONResponse(content={
        "success": True,
        "message": f"已删除 {ok} 个，失败 {fail} 个",
        "data": result,
    })
