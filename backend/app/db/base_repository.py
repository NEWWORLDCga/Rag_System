# -*- coding: utf-8 -*-
"""
Repository 基类
所有 Repository 继承此类，复用 pg_client 的参数化查询
"""
from typing import Any, Dict, List, Optional, Tuple
from app.db import pg_client


class BaseRepository:

    def _execute_sql(self, sql: str, params: Optional[Tuple] = None) -> None:
        pg_client.execute_sql(sql, params)

    def _execute_select(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        return pg_client.execute_select(sql, params)

    def _execute_returning(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        return pg_client.execute_returning(sql, params)

    def _execute_many(self, sql: str, params_list: List[Tuple]) -> None:
        pg_client.execute_many(sql, params_list)
