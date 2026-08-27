# -*- coding: utf-8 -*-
"""
文件列表业务逻辑
"""
import logging
from typing import Optional

from app.core.exceptions import NotFoundError
from app.db import get_file_repository, get_job_repository, get_chunk_repository, get_chunk_image_repository, get_kb_repository
from app.services.oss_service import get_oss_service

logger = logging.getLogger(__name__)


def list_files(kb_name: str, limit: int = 200) -> dict:
    kb = get_kb_repository().get_by_name(kb_name)
    if not kb:
        return {"files": [], "total": 0}
    files = get_file_repository().list_by_kb(kb["id"], limit=limit)
    # 附加最新 job 状态
    job_repo = get_job_repository()
    result = []
    for f in files:
        job = job_repo.get_by_file(f["id"])
        result.append({**f, "job": job})
    return {"files": result, "total": len(result)}


def delete_file(file_id: str) -> str:
    """
    联动删除：Milvus 向量 + OSS 图片 + PG 所有关联记录
    如果文件有 sync_graph 标识，同时删除知识图谱数据
    返回被删除的 file_name
    """
    file_repo = get_file_repository()
    file_record = file_repo.get_by_id(file_id)
    if not file_record:
        raise NotFoundError("文件记录不存在")

    file_name = file_record["file_name"]
    kb_id = file_record["kb_id"]
    sync_graph = file_record.get("sync_graph", False)

    # 获取 kb_name 用于 Milvus 操作
    kb = get_kb_repository().get_by_id(kb_id)
    kb_name = kb["name"] if kb else None

    # 1. 获取该文件所有 job
    job_repo = get_job_repository()
    job = job_repo.get_by_file(file_id)

    if job and kb_name:
        job_id = job["id"]

        # 2. Milvus 删除向量
        try:
            from app.services.milvus_service import get_milvus_service
            get_milvus_service().delete_by_job(kb_name, job_id)
        except Exception as e:
            logger.warning("Milvus 删除失败（继续）", extra={"job_id": job_id, "error": str(e)})

        # 3. 知识图谱删除（如果有 sync_graph 标识）
        if sync_graph:
            try:
                from app.services.kg_graph_sync_service import get_kg_graph_sync_service
                import asyncio
                kg_sync = get_kg_graph_sync_service()
                asyncio.get_event_loop().run_until_complete(
                    kg_sync.delete_graph_by_job(job_id)
                )
                logger.info(f"[delete_file] 知识图谱已删除 job_id={job_id}")
            except Exception as e:
                logger.error(f"[delete_file] 知识图谱删除失败（继续）: {e}")

        # 4. OSS 图片删除
        try:
            img_repo = get_chunk_image_repository()
            oss_keys = img_repo.get_oss_keys_by_job(job_id)
            if oss_keys:
                get_oss_service().delete_objects(oss_keys)
        except Exception as e:
            logger.warning("OSS 图片删除失败（继续）", extra={"error": str(e)})

    # 5. PG 级联删除（knowledge_file → knowledge_job → knowledge_chunk → knowledge_chunk_image）
    # 如果关联了 __default__ 类目文件记录，一并清理
    category_file_id = file_record.get("category_file_id")
    if category_file_id:
        try:
            from app.db import get_category_file_repository, get_category_repository
            cat_file_repo = get_category_file_repository()
            cat_file = cat_file_repo.get_by_id(category_file_id)
            if cat_file:
                cat_repo = get_category_repository()
                cat = cat_repo.get(cat_file["category_id"])
                if cat and cat["name"] == "__default__":
                    cat_file_repo.delete(category_file_id)
        except Exception as e:
            logger.warning(f"清理 __default__ 类目文件记录失败（继续）: {e}")

    file_repo.delete(file_id)

    logger.info(f"文件已删除: {file_name}, sync_graph={sync_graph}")
    return file_name


def batch_delete_files(file_ids: list, kb_name: str) -> dict:
    deleted, failed = [], []
    for file_id in file_ids:
        try:
            file_name = delete_file(file_id)
            deleted.append(file_name)
        except Exception as e:
            logger.error("批量删除单文件失败", extra={"file_id": file_id, "error": str(e)})
            failed.append({"file_id": file_id, "error": str(e)})
    return {"deleted": deleted, "failed": failed}
