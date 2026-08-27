# -*- coding: utf-8 -*-
"""知识图谱 API — 供前端调用，查询已同步到图谱的知识库"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.services import file_service
from app.services import kg_graph_sync_service
from app.db import get_kb_repository

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


@router.get("/kb/{kb_name}")
async def get_kb_graph(kb_name: str):
    """
    查询知识库下所有已同步到图谱的文件及其图谱数据。

    返回该知识库中所有标记了 sync_graph=true 的文件，
    以及每个文件对应的图谱 triples。
    """
    kb = get_kb_repository().get_by_name(kb_name)
    if not kb:
        raise HTTPException(status_code=404, detail=f"知识库「{kb_name}」不存在")

    # 获取该知识库下所有已同步到图谱的文件
    files_result = file_service.list_files(kb_name, limit=1000)
    synced_files = [
        f for f in files_result.get("files", [])
        if f.get("sync_graph") and f.get("job")
    ]

    if not synced_files:
        return JSONResponse(content={
            "success": True,
            "data": {"kb_name": kb_name, "files": [], "total_files": 0, "total_triples": 0},
        })

    # 批量查询每个文件的图谱 triples
    all_triples = []
    file_graphs = []

    for f in synced_files:
        job = f.get("job") or {}
        job_id = job.get("id") if isinstance(job, dict) else None
        if not job_id:
            continue

        try:
            kg_sync = kg_graph_sync_service.get_kg_graph_sync_service()
            result = await kg_sync.query_graph(job_id=job_id, kb_name=kb_name)
            triples = result.get("triples", [])
            all_triples.extend(triples)
            file_graphs.append({
                "file_id": f["id"],
                "file_name": f["file_name"],
                "job_id": job_id,
                "triples_count": len(triples),
                "triples": triples,
            })
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"查询图谱失败 file={f['file_name']}: {e}")
            file_graphs.append({
                "file_id": f["id"],
                "file_name": f["file_name"],
                "job_id": job_id,
                "triples_count": 0,
                "triples": [],
                "error": str(e),
            })

    return JSONResponse(content={
        "success": True,
        "data": {
            "kb_name": kb_name,
            "files": file_graphs,
            "total_files": len(file_graphs),
            "total_triples": len(all_triples),
        },
    })
