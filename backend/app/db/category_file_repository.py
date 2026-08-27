# -*- coding: utf-8 -*-
"""
类目文件仓储
表：knowledge_category_file
"""
import logging
from typing import Any, Dict, List, Optional
from app.db.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class CategoryFileRepository(BaseRepository):

    def create(self, *, category_id: str, file_name: str, oss_key: str) -> Dict[str, Any]:
        rows = self._execute_returning(
            "INSERT INTO knowledge_category_file(category_id, file_name, oss_key) VALUES (%s, %s, %s) RETURNING *",
            (category_id, file_name, oss_key),
        )
        return self._normalize(rows[0]) if rows else {}

    def get_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM knowledge_category_file WHERE id = %s LIMIT 1", (file_id,)
        )
        return self._normalize(rows[0]) if rows else None

    def get_by_category_and_filename(self, category_id: str, file_name: str) -> Optional[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM knowledge_category_file WHERE category_id = %s AND file_name = %s LIMIT 1",
            (category_id, file_name),
        )
        return self._normalize(rows[0]) if rows else None

    def list_by_category(self, category_id: str) -> List[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM knowledge_category_file WHERE category_id = %s ORDER BY created_at DESC",
            (category_id,),
        )
        return [self._normalize(r) for r in rows]

    def count_by_category(self, category_id: str) -> int:
        rows = self._execute_select(
            "SELECT COUNT(*) AS cnt FROM knowledge_category_file WHERE category_id = %s",
            (category_id,),
        )
        return int(rows[0]["cnt"]) if rows else 0

    def delete(self, file_id: str):
        self._execute_sql("DELETE FROM knowledge_category_file WHERE id = %s", (file_id,))

    def delete_by_category_and_filename(self, category_id: str, file_name: str):
        self._execute_sql(
            "DELETE FROM knowledge_category_file WHERE category_id = %s AND file_name = %s",
            (category_id, file_name),
        )

    @staticmethod
    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(row["id"]),
            "category_id": str(row["category_id"]),
            "file_name": row["file_name"],
            "oss_key": row["oss_key"],
            "created_at": str(row["created_at"]) if row.get("created_at") else None,
        }


_instance: Optional[CategoryFileRepository] = None


def get_category_file_repository() -> CategoryFileRepository:
    global _instance
    if _instance is None:
        _instance = CategoryFileRepository()
    return _instance
