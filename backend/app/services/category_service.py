# -*- coding: utf-8 -*-
"""
类目业务逻辑
"""
import logging
from typing import Optional

from app.core.exceptions import NotFoundError, ValidationError, ExternalServiceError
from app.db import get_category_repository, get_category_file_repository
from app.services.oss_service import get_oss_service

logger = logging.getLogger(__name__)


DEFAULT_CATEGORY_NAME = "__default__"


def get_or_create_default_category() -> dict:
    """获取或创建系统默认类目（单文件直传使用）"""
    repo = get_category_repository()
    cat = repo.get_by_name(DEFAULT_CATEGORY_NAME)
    if not cat:
        cat = repo.create(name=DEFAULT_CATEGORY_NAME, description="系统默认类目，单文件直传使用")
    return cat


def list_categories() -> dict:
    """列出所有类目，过滤掉系统内部的 __default__ 类目"""
    categories = [
        c for c in get_category_repository().list_all()
        if c["name"] != DEFAULT_CATEGORY_NAME
    ]
    return {"categories": categories, "total": len(categories)}


def create_category(name: str, description: Optional[str] = None) -> dict:
    return get_category_repository().create(name=name, description=description)


def get_category_with_files(category_id: str) -> dict:
    category = get_category_repository().get(category_id)
    if not category:
        raise NotFoundError("类目不存在")
    files = get_category_file_repository().list_by_category(category_id)
    return {"category": category, "files": files, "file_count": len(files)}


def update_category(category_id: str, name: Optional[str], description: Optional[str]) -> dict:
    repo = get_category_repository()
    if not repo.get(category_id):
        raise NotFoundError("类目不存在")
    repo.update(category_id, name=name, description=description)
    return repo.get(category_id)


def delete_category(category_id: str) -> None:
    cat_repo = get_category_repository()
    cat_file_repo = get_category_file_repository()
    cat = cat_repo.get(category_id)
    if not cat:
        raise NotFoundError("类目不存在")
    if cat["name"] == DEFAULT_CATEGORY_NAME:
        raise ValidationError("系统默认类目不可删除")
    count = cat_file_repo.count_by_category(category_id)
    if count > 0:
        raise ValidationError(f"类目下还有 {count} 个文件，请先删除文件")
    cat_repo.delete(category_id)


def delete_category_file(category_id: str, file_id: str) -> str:
    cat_file_repo = get_category_file_repository()
    record = cat_file_repo.get_by_id(file_id)
    if not record or record["category_id"] != category_id:
        raise NotFoundError("文件记录不存在")

    oss_key = record.get("oss_key")
    if oss_key:
        try:
            get_oss_service().delete_objects([oss_key])
        except Exception as e:
            logger.warning("OSS 删除失败（继续）", extra={"oss_key": oss_key, "error": str(e)})

    cat_file_repo.delete(file_id)
    return record["file_name"]


def batch_delete_category_files(category_id: str, file_ids: list) -> dict:
    cat_file_repo = get_category_file_repository()
    oss_keys, deleted, not_found = [], [], []
    for fid in file_ids:
        record = cat_file_repo.get_by_id(fid)
        if not record or record["category_id"] != category_id:
            not_found.append(fid)
            continue
        if record.get("oss_key"):
            oss_keys.append(record["oss_key"])
        deleted.append(record["file_name"])

    if oss_keys:
        try:
            get_oss_service().delete_objects(oss_keys)
        except Exception as e:
            logger.warning("OSS 批量删除失败（继续）", extra={"error": str(e)})

    for fid in file_ids:
        record = cat_file_repo.get_by_id(fid)
        if record and record["category_id"] == category_id:
            cat_file_repo.delete(fid)

    return {"deleted": deleted, "not_found": not_found}
