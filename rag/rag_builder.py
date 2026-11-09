import os
import sys
import asyncio
from openai import OpenAI
from raganything import RAGAnything, RAGAnythingConfig
from lightrag.utils import EmbeddingFunc



WORKING_DIR = "./rag_storage"
OUTPUT_DIR = "./output"
EMBED_DIM = 1024


def build_rag() -> RAGAnything:
    """Create a RAGAnything instance bound to the shared on-disk storage."""
    config = RAGAnythingConfig(
        working_dir=WORKING_DIR,
        parser="mineru",
        parse_method="auto",
        enable_image_processing=False,
        enable_table_processing=True,
        enable_equation_processing=True,
    )
    rag = RAGAnything(
        config=config,
        llm_model_func=lmstudio_llm_model_func,
        embedding_func=EmbeddingFunc(
            embedding_dim=EMBED_DIM,
            max_token_size=8192,
            func=embedding_func,
        ),
    )
    # Compatibility: older LightRAG rejects the extra 'multimodal_processed' field.
    async def _noop_mark_multimodal(doc_id: str):
        return None

    rag._mark_multimodal_processing_complete = _noop_mark_multimodal
    return rag