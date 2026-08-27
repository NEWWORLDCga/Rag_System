# -*- coding: utf-8 -*-
"""
知识库仓储
表：knowledge_base
"""
import logging
from typing import Any, Dict, List, Optional
from app.db.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class KbRepository(BaseRepository):

    def create(
        self,
        *,
        name: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        image_mode: bool = False,
        kb_type: str = "standard",
        embedding_model: str = "text-embedding-v3",
        vector_dim: int = 1536,
        metadata_fields: Optional[list] = None,
        retrieval_config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        import json
        rows = self._execute_returning(
            """
            INSERT INTO knowledge_base(name, display_name, description, image_mode, kb_type, embedding_model, vector_dim, metadata_fields, retrieval_config)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (name, display_name or name, description, image_mode, kb_type, embedding_model, vector_dim,
             json.dumps(metadata_fields or []), json.dumps(retrieval_config or {})),
        )
        return self._normalize(rows[0]) if rows else {}

    def get_by_id(self, kb_id: str) -> Optional[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM knowledge_base WHERE id = %s LIMIT 1", (kb_id,)
        )
        return self._normalize(rows[0]) if rows else None

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM knowledge_base WHERE name = %s LIMIT 1", (name,)
        )
        return self._normalize(rows[0]) if rows else None

    def list_all(self) -> List[Dict[str, Any]]:
        rows = self._execute_select(
            "SELECT * FROM knowledge_base ORDER BY created_at DESC"
        )
        return [self._normalize(r) for r in rows]

    def update(
        self,
        kb_id: str,
        *,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        image_mode: Optional[bool] = None,
        embedding_model: Optional[str] = None,
        vector_dim: Optional[int] = None,
        retrieval_config: Optional[dict] = None,
    ) -> Optional[Dict[str, Any]]:
        import json
        parts, params = [], []
        if display_name is not None:
            parts.append("display_name = %s"); params.append(display_name)
        if description is not None:
            parts.append("description = %s"); params.append(description)
        if image_mode is not None:
            parts.append("image_mode = %s"); params.append(image_mode)
        if embedding_model is not None:
            parts.append("embedding_model = %s"); params.append(embedding_model)
        if vector_dim is not None:
            parts.append("vector_dim = %s"); params.append(vector_dim)
        if retrieval_config is not None:
            parts.append("retrieval_config = %s"); params.append(json.dumps(retrieval_config))
        if not parts:
            return self.get_by_id(kb_id)
        parts.append("updated_at = NOW()")
        params.append(kb_id)
        self._execute_sql(f"UPDATE knowledge_base SET {', '.join(parts)} WHERE id = %s", tuple(params))
        return self.get_by_id(kb_id)

    def delete(self, kb_id: str) -> None:
        self._execute_sql("DELETE FROM knowledge_base WHERE id = %s", (kb_id,))

    @staticmethod
    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        import json
        mf = row.get("metadata_fields")
        if isinstance(mf, str):
            try:
                mf = json.loads(mf)
            except Exception:
                mf = []
        rc = row.get("retrieval_config")
        if isinstance(rc, str):
            try:
                rc = json.loads(rc)
            except Exception:
                rc = {}
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "display_name": row.get("display_name"),
            "description": row.get("description"),
            "image_mode": bool(row.get("image_mode", False)),
            "kb_type": row.get("kb_type", "standard"),
            "embedding_model": row.get("embedding_model", "text-embedding-v3"),
            "vector_dim": row.get("vector_dim", 1536),
            "metadata_fields": mf or [],
            "retrieval_config": rc or {},
            "created_at": str(row["created_at"]) if row.get("created_at") else None,
            "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
        }


_instance: Optional[KbRepository] = None


def get_kb_repository() -> KbRepository:
    global _instance
    if _instance is None:
        _instance = KbRepository()
    return _instance
