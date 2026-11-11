from lightrag.utils import EmbeddingFunc
from raganything import RAGAnything, RAGAnythingConfig


def build_rag(WORKING_DIR, llm_model_func, embedding_func, EMBED_DIM) -> RAGAnything:
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
        llm_model_func=llm_model_func,
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
