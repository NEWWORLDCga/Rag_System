# -*- coding: utf-8 -*-
"""
类目仓储
表：knowledge_category
"""
import logging
from typing import Any, Dict, List, Optional
from app.db.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class CategoryRepository(BaseRepository):

    def create(self, *, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        rows = self._execute_returning(
            "INSERT INTO knowledge_category(name, description) VALUES (%s, %s) RETURNING *",
            (name, description),
        )
        return self._normalize(rows[0]) if rows else {}

    def get(self, category_id: str) -> Optional[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM knowledge_category WHERE id = %s LIMIT 1", (category_id,)
        )
        return self._normalize(rows[0]) if rows else None

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM knowledge_category WHERE name = %s LIMIT 1", (name,)
        )
        return self._normalize(rows[0]) if rows else None

    def list_all(self) -> List[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM knowledge_category ORDER BY created_at DESC"
        )
        return [self._normalize(r) for r in rows]

    def update(self, category_id: str, *, name: Optional[str] = None, description: Optional[str] = None):
        parts, params = ["updated_at = NOW()"], []
        if name is not None:
            parts.append("name = %s"); params.append(name)
        if description is not None:
            parts.append("description = %s"); params.append(description)
        params.append(category_id)
        self._execute_sql(
            f"UPDATE knowledge_category SET {', '.join(parts)} WHERE id = %s", tuple(params)
        )

    def delete(self, category_id: str):
        self._execute_sql("DELETE FROM knowledge_category WHERE id = %s", (category_id,))

    @staticmethod
    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(row["id"]),
            "category_id": str(row["id"]),  # 兼容旧接口
            "name": row["name"],
            "description": row.get("description"),
            "created_at": str(row["created_at"]) if row.get("created_at") else None,
            "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
        }


_instance: Optional[CategoryRepository] = None


def get_category_repository() -> CategoryRepository:
    global _instance
    if _instance is None:
        _instance = CategoryRepository()
    return _instance
