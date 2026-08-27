"""Configuration settings for the application.

This module defines the configuration settings using Pydantic's
SettingsConfigDict to load environment variables from a .env file.
"""

import logging
from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("uvicorn")


class Qdrant(BaseSettings):
    """Qdrant connection configuration."""

    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    location: Optional[str] = None
    url: Optional[str] = None
    port: Optional[int] = 6333
    grpc_port: int = 6334
    prefer_grpc: bool = False
    https: Optional[bool] = None
    api_key: Optional[str] = None
    prefix: Optional[str] = None
    timeout: Optional[int] = None
    host: Optional[str] = None
    path: Optional[str] = None


class Settings(BaseSettings):
    """Settings class for the application."""

    # ENVIRONMENT CONFIG
    environment: str = "dev"
    testing: bool = bool(0)

    # API CONFIG
    project_name: str = "Knowledge Table API"
    api_v1_str: str = "/api/v1"
    backend_cors_origins: List[str] = ["*"]

    # LLM / Embedding 配置（OpenAI SDK，base_url 指向百炼兼容端点）
    # provider 仍用 "openai"（SDK 不变，url 变）
    dimensions: int = 1024
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-v3"
    llm_provider: str = "openai"
    llm_model: str = "qwen-plus"

    # 百炼 OpenAI 兼容配置
    openai_api_key: str = "sk-42c18e29a0534cdb9cffb4bea68d93c9"   # 从 .env 读
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # VECTOR DATABASE CONFIG
    vector_db_provider: str = "milvus"
    index_name: str = "milvus"

    # MILVUS CONFIG（共用主项目 Milvus）
    milvus_db_uri: str = "http://milvus-standalone:19530"
    milvus_db_token: str = ""

    # QDRANT CONFIG
    qdrant: Qdrant = Field(default_factory=lambda: Qdrant())

    # POSTGRESQL CONFIG（共用主项目 kb-postgres，用于存储图谱 triples 元数据）
    kt_pg_host: str = "kb-postgres"
    kt_pg_port: int = 5432
    kt_pg_db: str = "knowledge_db"
    kt_pg_user: str = "kbuser"
    kt_pg_password: str = "kbpass"

    # QUERY CONFIG
    query_type: str = "hybrid"

    # DOCUMENT PROCESSING CONFIG
    loader: str = "pypdf"
    chunk_size: int = 512
    chunk_overlap: int = 64

    # UNSTRUCTURED CONFIG
    unstructured_api_key: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="_",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get the settings for the application."""
    logger.info("Loading config settings from the environment...")
    return Settings()