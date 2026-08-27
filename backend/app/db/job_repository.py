# -*- coding: utf-8 -*-
"""
处理任务仓储
表：knowledge_job
自维护状态机：pending → chunking → chunked → embedding → done / error
"""
import logging
from typing import Any, Dict, List, Optional
from app.db.base_repository import BaseRepository

logger = logging.getLogger(__name__)

# 合法状态
VALID_STATUSES = {"pending", "chunking", "chunked", "embedding", "done", "error"}


class JobRepository(BaseRepository):

    def create(self, *, file_id: str, kb_id: str) -> Dict[str, Any]:
        rows = self._execute_returning(
            "INSERT INTO knowledge_job(file_id, kb_id) VALUES (%s, %s) RETURNING *",
            (file_id, kb_id),
        )
        return self._normalize(rows[0]) if rows else {}

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM knowledge_job WHERE id = %s LIMIT 1", (job_id,)
        )
        return self._normalize(rows[0]) if rows else None

    def get_by_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """获取文件最新的 job"""
        rows = self._execute_select(
            "SELECT * FROM knowledge_job WHERE file_id = %s ORDER BY created_at DESC LIMIT 1",
            (file_id,),
        )
        return self._normalize(rows[0]) if rows else None

    def list_by_kb(self, kb_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        rows = self._execute_select(
            """
            SELECT j.*, f.file_name, f.oss_key, f.status AS file_status
            FROM knowledge_job j
            JOIN knowledge_file f ON j.file_id = f.id
            WHERE j.kb_id = %s
            ORDER BY j.created_at DESC
            LIMIT %s
            """,
            (kb_id, limit),
        )
        return [self._normalize(r) for r in rows]

    def update_status(
        self,
        job_id: str,
        status: str,
        *,
        stage: Optional[str] = None,
        progress: Optional[int] = None,
        chunk_count: Optional[int] = None,
        error_msg: Optional[str] = None,
    ):
        parts = ["status = %s", "updated_at = NOW()"]
        params: List[Any] = [status]
        if stage is not None:
            parts.append("stage = %s"); params.append(stage)
        if progress is not None:
            parts.append("progress = %s"); params.append(progress)
        if chunk_count is not None:
            parts.append("chunk_count = %s"); params.append(chunk_count)
        if error_msg is not None:
            parts.append("error_msg = %s"); params.append(error_msg)
        params.append(job_id)
        self._execute_sql(
            f"UPDATE knowledge_job SET {', '.join(parts)} WHERE id = %s", tuple(params)
        )

    def mark_vectorized(self, job_id: str):
        self._execute_sql(
            "UPDATE knowledge_job SET vectorized = TRUE, status = 'done', progress = 100, updated_at = NOW() WHERE id = %s",
            (job_id,),
        )

    def delete(self, job_id: str):
        self._execute_sql("DELETE FROM knowledge_job WHERE id = %s", (job_id,))

    def delete_by_file(self, file_id: str):
        self._execute_sql("DELETE FROM knowledge_job WHERE file_id = %s", (file_id,))

    @staticmethod
    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(row["id"]),
            "job_id": str(row["id"]),  # 兼容旧接口
            "file_id": str(row["file_id"]),
            "kb_id": str(row["kb_id"]),
            "status": row.get("status", "pending"),
            "stage": row.get("stage"),
            "progress": row.get("progress", 0),
            "chunk_count": row.get("chunk_count"),
            "vectorized": bool(row.get("vectorized", False)),
            "error_msg": row.get("error_msg"),
            # 来自 JOIN knowledge_file 的字段（list_by_kb 时有）
            "file_name": row.get("file_name"),
            "oss_key": row.get("oss_key"),
            "created_at": str(row["created_at"]) if row.get("created_at") else None,
            "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
        }


_instance: Optional[JobRepository] = None


def get_job_repository() -> JobRepository:
    global _instance
    if _instance is None:
        _instance = JobRepository()
    return _instance
