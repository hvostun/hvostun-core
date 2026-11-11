"""
LM Studio + RAG-Anything PDF example.

Two phases, run separately so the knowledge base persists on disk:

    # 1. Build the RAG storage from a PDF (parses + indexes into ./rag_storage_pdf)
    python local_rag.py build path/to/document.pdf

    # 2. Ask questions against the storage built above
    python local_rag.py query "What is the document about?" [mode]

`mode` is a LightRAG query mode (hybrid, local, global, mix, naive); default hybrid.

Reuses the LM Studio LLM/embedding functions from lmstudio_ex.py.
"""

import asyncio
import json
import os
import sys

import numpy as np
import requests
from dotenv import load_dotenv
from lightrag.llm.openai import openai_complete_if_cache
from openai import (
    OpenAI,
    RateLimitError,  # Убедитесь, что импорт корректен
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from utils import build_rag

TOKEN = None
GLOBAL_COUNTER = 0
load_dotenv("env.local")

AUTH_URL = os.environ["AUTH_URL"]
CHAT_URL = os.environ["CHAT_URL"]
RqUID = os.environ["RqUID"]
ATOKEN = os.environ["ATOKEN"]
CHAT_MODEL = os.environ["CHAT_MODEL"]

EMBED_URL = os.environ["EMBED_URL"]
EMBED_KEY = os.environ["EMBED_TOKEN"]
EMBED_MODEL = os.environ["EMBED_MODEL"]
EMBED_DIM = int(os.environ["EMBED_DIM"])

WORKING_DIR = os.environ["WORKING_DIR"]
OUTPUT_DIR = os.environ["OUTPUT_DIR"]


async def embedding_func(texts: list[str]):
    client = OpenAI(api_key=EMBED_KEY, base_url=EMBED_URL)
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return np.array([d.embedding for d in response.data])


@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(5),  # Максимум 5 попыток
    wait=wait_exponential(multiplier=1, min=4, max=15),  # Экспоненциальная задержка
    reraise=True,
)
async def llm_model_func(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list[dict] = None,
    **kwargs,
) -> str:
    global GLOBAL_COUNTER
    GLOBAL_COUNTER += 1
    if GLOBAL_COUNTER == 10:
        auth()

    """Top-level LLM function for LightRAG (pickle-safe)."""
    return await openai_complete_if_cache(
        model=CHAT_MODEL,
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages or [],
        base_url=CHAT_URL,
        api_key=TOKEN,
        **kwargs,
    )


def auth():
    global TOKEN
    global GLOBAL_COUNTER
    GLOBAL_COUNTER = 0
    payload = {"scope": "GIGACHAT_API_PERS"}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": RqUID,
        "Authorization": f"Basic {ATOKEN}",
    }
    response = requests.request("POST", AUTH_URL, headers=headers, data=payload)
    payload = json.loads(response.text)
    print(payload["expires_at"])
    TOKEN = payload["access_token"]

    headers = {"Accept": "application/json", "Authorization": f"Bearer {TOKEN}"}
    response = requests.request("GET", CHAT_URL + "/models", headers=headers, data={})
    print(json.loads(response.text))


async def build(pdf_path: str) -> None:
    if not os.path.isfile(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)

    print(f"📄 Building storage from {pdf_path} -> {WORKING_DIR}")
    rag = build_rag(WORKING_DIR, llm_model_func, embedding_func, EMBED_DIM)
    try:
        await rag.process_document_complete(
            file_path=pdf_path,
            output_dir=OUTPUT_DIR,
            parse_method="auto",
            display_stats=True,
        )
    finally:
        await rag.finalize_storages()
    print(f'✅ Storage built. Now query it with:\n   python {sys.argv[0]} query "..."')


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

    auth()
    GLOBAL_COUNTER

    command = args[0]
    if command == "build" or command == "b":
        if len(args) < 2:
            print("Usage: python local_rag.py build <pdf_path>")
            sys.exit(1)
        asyncio.run(build(args[1]))

    elif command == "query" or command == "q":
        if len(args) < 2:
            print('Usage: python local_rag.py query "<question>" [mode]')
            sys.exit(1)
        asyncio.run(query(args[1], args[2] if len(args) > 2 else "hybrid"))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
