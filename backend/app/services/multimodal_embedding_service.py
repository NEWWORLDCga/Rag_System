# -*- coding: utf-8 -*-
"""
多模态 Embedding 服务
使用 qwen3-vl-embedding 对文本和图片分别生成独立向量（共享语义空间）。
enable_fusion=False：文本和图片各自输出独立向量，维度相同，可在同一 Milvus 字段检索。
"""
import logging
import time
from typing import List, Optional

import dashscope
from dashscope import MultiModalEmbedding

from app.core.config import settings

logger = logging.getLogger(__name__)

MULTIMODAL_MODEL = "qwen3-vl-embedding"
# qwen3-vl-embedding 支持的维度：2560/2048/1536/1024/768/512/256，默认 1024
DEFAULT_IMAGE_DIM = 1024


class MultimodalEmbeddingService:

    def __init__(self):
        dashscope.api_key = settings.dashscope_api_key

    def embed_text(self, text: str, dimension: int = DEFAULT_IMAGE_DIM, retry: int = 3) -> List[float]:
        """用 qwen3-vl-embedding 对文本生成向量（与图片向量在同一语义空间）"""
        return self._call([{"text": text}], dimension, retry)

    def embed_texts(self, texts: List[str], dimension: int = DEFAULT_IMAGE_DIM) -> List[List[float]]:
        """批量文本向量化，逐条调用（qwen3-vl-embedding 不支持批量文本）"""
        return [self.embed_text(t, dimension) for t in texts]

    def embed_image(self, image_url: str, dimension: int = DEFAULT_IMAGE_DIM, retry: int = 3) -> Optional[List[float]]:
        """用 qwen3-vl-embedding 对图片 URL 生成向量"""
        try:
            return self._call([{"image": image_url}], dimension, retry)
        except Exception as e:
            logger.warning(f"[MultimodalEmbed] 图片向量化失败，跳过: {image_url[:80]}, error={e}")
            return None

    def embed_text_and_image(
        self, text: str, image_url: str, dimension: int = DEFAULT_IMAGE_DIM
    ) -> dict:
        """同时生成文本和图片向量，返回 {'text': [...], 'image': [...]}"""
        return {
            "text": self.embed_text(text, dimension),
            "image": self.embed_image(image_url, dimension),
        }

    def _call(self, inputs: list, dimension: int, retry: int = 3) -> List[float]:
        for attempt in range(retry):
            try:
                resp = MultiModalEmbedding.call(
                    api_key=settings.dashscope_api_key,
                    model=MULTIMODAL_MODEL,
                    input=inputs,
                    enable_fusion=False,  # 独立向量模式，文字和图片各自输出
                    dimension=dimension,
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"qwen3-vl-embedding 调用失败: {resp.message}")
                # 返回第一个结果的 embedding
                return resp.output["embeddings"][0]["embedding"]
            except Exception as e:
                if attempt < retry - 1:
                    wait = 2 ** attempt
                    logger.warning(f"[MultimodalEmbed] 调用失败，{wait}s 后重试 ({attempt+1}/{retry}): {e}")
                    time.sleep(wait)
                else:
                    logger.error(f"[MultimodalEmbed] 最终失败: {e}")
                    raise
        return []


_instance: Optional[MultimodalEmbeddingService] = None


def get_multimodal_embedding_service() -> MultimodalEmbeddingService:
    global _instance
    if _instance is None:
        _instance = MultimodalEmbeddingService()
    return _instance
