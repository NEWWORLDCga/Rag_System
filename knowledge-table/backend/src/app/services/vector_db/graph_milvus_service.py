"""Knowledge Graph Milvus service — 图谱 triples 的向量存储和检索."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, TYPE_CHECKING

from pymilvus import DataType, MilvusClient

from app.core.config import Settings

if TYPE_CHECKING:
    from app.services.embedding.base import EmbeddingService

logger = logging.getLogger(__name__)

GRAPH_COLLECTION_NAME = "knowledge_graph"


class GraphMilvusService:
    """图谱 triples 的 Milvus 存储服务（与 chunks collection 完全隔离）."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = MilvusClient(
            uri=settings.milvus_db_uri,
            token=settings.milvus_db_token,
        )

    async def ensure_collection_exists(self) -> None:
        """确保 knowledge_graph collection 存在."""
        try:
            # 检查 collection 是否存在且结构正确
            needs_recreate = False
            if self.client.has_collection(GRAPH_COLLECTION_NAME):
                try:
                    schema = self.client.describe_collection(GRAPH_COLLECTION_NAME)
                    fields = {f["name"] for f in schema.get("fields", [])}
                    # 检查是否缺少 embedding 字段
                    if "embedding" not in fields:
                        logger.info(f"Collection {GRAPH_COLLECTION_NAME} missing embedding field, recreating...")
                        needs_recreate = True
                        self.client.drop_collection(GRAPH_COLLECTION_NAME)
                except Exception as e:
                    logger.warning(f"Error describing collection: {e}, will recreate")
                    needs_recreate = True
                    self.client.drop_collection(GRAPH_COLLECTION_NAME)

            if needs_recreate or not self.client.has_collection(GRAPH_COLLECTION_NAME):
                schema = self.client.create_schema(
                    auto_id=False,
                    enable_dynamic_field=True,
                )
                schema.add_field(
                    field_name="triple_id",
                    datatype=DataType.VARCHAR,
                    is_primary=True,
                    max_length=64,
                )
                schema.add_field(
                    field_name="job_id",
                    datatype=DataType.VARCHAR,
                    max_length=64,
                )
                schema.add_field(
                    field_name="kb_name",
                    datatype=DataType.VARCHAR,
                    max_length=256,
                )
                schema.add_field(
                    field_name="file_name",
                    datatype=DataType.VARCHAR,
                    max_length=512,
                )
                schema.add_field(
                    field_name="head_chunk_id",
                    datatype=DataType.VARCHAR,
                    max_length=64,
                )
                schema.add_field(
                    field_name="head_content",
                    datatype=DataType.VARCHAR,
                    max_length=8192,
                )
                schema.add_field(
                    field_name="tail_chunk_id",
                    datatype=DataType.VARCHAR,
                    max_length=64,
                )
                schema.add_field(
                    field_name="tail_content",
                    datatype=DataType.VARCHAR,
                    max_length=8192,
                )
                schema.add_field(
                    field_name="relation",
                    datatype=DataType.VARCHAR,
                    max_length=64,
                )
                # 添加向量字段以满足 Milvus 要求，维度与主项目一致（1024）
                schema.add_field(
                    field_name="embedding",
                    datatype=DataType.FLOAT_VECTOR,
                    dim=1024,
                )

                index_params = self.client.prepare_index_params()
                index_params.add_index(
                    index_type="AUTOINDEX",
                    field_name="job_id",
                )
                index_params.add_index(
                    index_type="AUTOINDEX",
                    field_name="embedding",
                )

                self.client.create_collection(
                    collection_name=GRAPH_COLLECTION_NAME,
                    schema=schema,
                    index_params=index_params,
                    consistency_level=0,
                )
                logger.info(f"Collection {GRAPH_COLLECTION_NAME} created.")
            else:
                logger.info(f"Collection {GRAPH_COLLECTION_NAME} already exists with correct schema.")
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            raise

    async def upsert_triples(
        self,
        triples: List[Dict[str, Any]],
        embedding_service: EmbeddingService = None,
    ) -> Dict[str, Any]:
        """批量写入 triples 到 Milvus，包含语义向量."""
        await self.ensure_collection_exists()

        batch_size = 1000
        total_inserted = 0

        for i in range(0, len(triples), batch_size):
            batch = triples[i: i + batch_size]
            # 为每个 triple 生成或使用已有的向量
            for triple in batch:
                head_vec = triple.pop("_head_vector", [])
                tail_vec = triple.pop("_tail_vector", [])

                if head_vec and tail_vec and len(head_vec) == len(tail_vec):
                    # 使用 head + tail 向量的平均值作为 triple 的向量
                    triple["embedding"] = [
                        (h + t) / 2 for h, t in zip(head_vec, tail_vec)
                    ]
                    logger.debug("[GraphSync] triple=%s embedding=(head+tail)/2 dim=%d sample=%s",
                                 triple.get("triple_id"), len(triple["embedding"]),
                                 triple["embedding"][:3])
                elif head_vec:
                    triple["embedding"] = head_vec
                    logger.debug("[GraphSync] triple=%s embedding=head_only dim=%d",
                                 triple.get("triple_id"), len(triple["embedding"]))
                elif tail_vec:
                    triple["embedding"] = tail_vec
                    logger.debug("[GraphSync] triple=%s embedding=tail_only dim=%d",
                                 triple.get("triple_id"), len(triple["embedding"]))
                else:
                    # 如果没有传入向量，生成组合文本的向量
                    combined_text = f"{triple.get('head_content', '')[:200]} {triple.get('relation', '')} {triple.get('tail_content', '')[:200]}"
                    if combined_text and embedding_service:
                        embeddings = await embedding_service.get_embeddings([combined_text])
                        triple["embedding"] = embeddings[0] if embeddings else [0.0] * 1024
                        logger.warning("[GraphSync] triple=%s NO vectors, generated from text dim=%d",
                                       triple.get("triple_id"), len(triple["embedding"]))
                    else:
                        triple["embedding"] = [0.0] * 1024
                        logger.warning("[GraphSync] triple=%s NO vectors, fallback zeros dim=1024",
                                       triple.get("triple_id"))

            resp = self.client.insert(
                collection_name=GRAPH_COLLECTION_NAME, data=batch
            )
            total_inserted += resp["insert_count"]
            logger.info(f"Inserted {resp['insert_count']} triples.")

        return {
            "message": f"Successfully upserted {total_inserted} triples.",
            "count": total_inserted,
        }

    async def query_by_job(self, job_id: str) -> List[Dict[str, Any]]:
        """根据 job_id 查询所有 triples."""
        try:
            resp = self.client.query(
                collection_name=GRAPH_COLLECTION_NAME,
                filter=f'job_id == "{job_id}"',
                output_fields=["*"],
            )
            return resp
        except Exception as e:
            logger.error(f"Error querying by job_id: {e}")
            return []

    async def delete_by_job(self, job_id: str) -> Dict[str, Any]:
        """根据 job_id 删除所有 triples."""
        try:
            self.client.delete(
                collection_name=GRAPH_COLLECTION_NAME,
                filter=f'job_id == "{job_id}"',
            )
            resp = self.client.query(
                collection_name=GRAPH_COLLECTION_NAME,
                filter=f'job_id == "{job_id}"',
                output_fields=["triple_id"],
            )
            remaining = len(resp)
            logger.info(f"Deleted triples for job_id={job_id}, remaining={remaining}")
            return {
                "deleted_count": remaining,
                "message": f"Deleted triples for job_id={job_id}.",
            }
        except Exception as e:
            logger.error(f"Error deleting by job_id: {e}")
            return {"deleted_count": 0, "message": str(e)}
