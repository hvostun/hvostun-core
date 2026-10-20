"""
LM Studio + RAG-Anything PDF example.

Two phases, run separately so the knowledge base persists on disk:

    # 1. Build the RAG storage from a PDF (parses + indexes into ./rag_storage_pdf)
    python lmstudio_pdf_rag.py build path/to/document.pdf

    # 2. Ask questions against the storage built above
    python lmstudio_pdf_rag.py query "What is the document about?" [mode]

`mode` is a LightRAG query mode (hybrid, local, global, mix, naive); default hybrid.

Reuses the LM Studio LLM/embedding functions from lmstudio_ex.py.
"""

import os
import sys
import asyncio

from raganything import RAGAnything, RAGAnythingConfig
from lightrag.utils import EmbeddingFunc

from lmstudio_ex import lmstudio_llm_model_func, lmstudio_embedding_func

WORKING_DIR = "./rag_storage_pdf"
OUTPUT_DIR = "./output_pdf"
EMBED_DIM = 768


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
            func=lmstudio_embedding_func,
        ),
    )

    # Compatibility: older LightRAG rejects the extra 'multimodal_processed' field.
    async def _noop_mark_multimodal(doc_id: str):
        return None

    rag._mark_multimodal_processing_complete = _noop_mark_multimodal
    return rag


async def build(pdf_path: str) -> None:
    if not os.path.isfile(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)

    print(f"📄 Building storage from {pdf_path} -> {WORKING_DIR}")
    rag = build_rag()
    try:
        await rag.process_document_complete(
            file_path=pdf_path,
            output_dir=OUTPUT_DIR,
            parse_method="auto",
            display_stats=True,
        )
    finally:
        await rag.finalize_storages()
    print(f"✅ Storage built. Now query it with:\n   python {sys.argv[0]} query \"...\"")


async def query(question: str, mode: str) -> None:
    if not os.path.isdir(WORKING_DIR):
        print(f"❌ No storage at {WORKING_DIR}. Run the 'build' step first.")
        sys.exit(1)

    print(f"🔍 [{mode}] {question}")
    rag = build_rag()
    try:
        answer = await rag.aquery(question, mode=mode)
    finally:
        await rag.finalize_storages()
    print(f"\n{answer}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    command = args[0]
    if command == "build":
        if len(args) < 2:
            print("Usage: python lmstudio_pdf_rag.py build <pdf_path>")
            sys.exit(1)
        asyncio.run(build(args[1]))
    elif command == "query":
        if len(args) < 2:
            print("Usage: python lmstudio_pdf_rag.py query \"<question>\" [mode]")
            sys.exit(1)
        asyncio.run(query(args[1], args[2] if len(args) > 2 else "hybrid"))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
