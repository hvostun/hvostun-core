"""
Simple FastAPI server over the LM Studio PDF RAG storage.

Reuses the RAG instance/config from lmstudio_pdf_rag.py and keeps one
RAGAnything alive for the whole process, so it can both ingest PDFs and answer
questions against the same ./rag_storage_pdf.

Run it:
    pip install fastapi uvicorn
    python pdf_rag_server.py
    # or: uvicorn pdf_rag_server:app --reload

Endpoints:
    GET  /health                     -> server + storage status
    POST /build  {"pdf_path": "..."} -> parse + index a PDF into the storage
    POST /query  {"query": "...", ...} -> ask a question

Query body fields:
    query                (required)
    mode                 hybrid | local | global | mix | naive | bypass  (default hybrid)
    system_prompt        the "system role" instruction for the answer
    temperature          LLM sampling temperature (per request)
    max_tokens           LLM max output tokens (per request)
    top_k, chunk_top_k   retrieval breadth
    only_need_context    return retrieved context instead of an answer
    response_type        e.g. "Bullet Points", "Single Paragraph"
    conversation_history [{"role": "...", "content": "..."}]
    user_prompt          extra instructions for the LLM
"""

import os
import json
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# RAG-Anything imports
from raganything import RAGAnything, RAGAnythingConfig
from lightrag.utils import EmbeddingFunc
from lightrag.llm.openai import openai_complete_if_cache, openai_embed


import uvicorn

import requests

import shutil
import uuid
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError # Убедитесь, что импорт корректен


from fastapi import FastAPI, File, HTTPException, UploadFile

from dotenv import load_dotenv
from utils import build_rag


TOKEN = None
GLOBAL_COUNTER = 0

load_dotenv('env.local')

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

async def embedding_func(texts: List[str]):
    client = OpenAI(
        api_key=EMBED_KEY,
        base_url=EMBED_URL
    )
    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    return np.array([d.embedding for d in response.data])


@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(5),  # Максимум 5 попыток
    wait=wait_exponential(multiplier=1, min=4, max=15), # Экспоненциальная задержка
    reraise=True
)
async def llm_model_func(
    prompt: str,
    system_prompt: Optional[str] = None,
    history_messages: List[Dict] = None,
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


state: Dict[str, Any] = {"rag": None, "gen_kwargs": {}}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # rag = build_rag()
    rag = build_rag(WORKING_DIR, llm_model_func, embedding_func, EMBED_DIM)
    await rag._ensure_lightrag_initialized()
    state["rag"] = rag
    print(f"✅ RAG ready (working_dir={WORKING_DIR})")
    try:
        yield
    finally:
        await rag.finalize_storages()


app = FastAPI(title="LM Studio PDF RAG", lifespan=lifespan)


class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_k: Optional[int] = None
    chunk_top_k: Optional[int] = None
    only_need_context: bool = False
    response_type: Optional[str] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None
    user_prompt: Optional[str] = None


def _apply_generation_kwargs(rag, temperature, max_tokens):
    """Bake per-request temperature/max_tokens into LightRAG's query role.

    LightRAG has no per-query generation params: the query role's kwargs are
    fixed when the LLM wrapper is built. update_llm_role_config rebuilds that
    wrapper, so we only do it when the values actually change.
    """
    gen = {}
    if temperature is not None:
        gen["temperature"] = temperature
    if max_tokens is not None:
        gen["max_tokens"] = max_tokens
    if gen == state["gen_kwargs"]:
        return
    merged = dict(
        rag.lightrag.role_llm_kwargs.get("query")
        or rag.lightrag.llm_model_kwargs
        or {}
    )
    merged.update(gen)
    rag.lightrag.update_llm_role_config("query", model_kwargs=merged)
    state["gen_kwargs"] = gen


@app.get("/health")
async def health():
    return {
        "ok": state["rag"] is not None,
        "working_dir": WORKING_DIR,
        "storage_exists": os.path.isdir(WORKING_DIR),
        "llm_model": CHAT_MODEL,
        "embedding_model": EMBED_MODEL,
        "embedding_dim": EMBED_DIM,
        "CHAT_URL": CHAT_URL,
        "EMBED_URL": EMBED_URL, 
    }


def auth():
    global TOKEN
    global GLOBAL_COUNTER
    GLOBAL_COUNTER = 0
    payload={'scope': 'GIGACHAT_API_PERS'}
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': RqUID,
        'Authorization': f'Basic {ATOKEN}'
    }
    response = requests.request("POST", AUTH_URL, headers=headers, data=payload)
    payload = json.loads(response.text)
    print(payload['expires_at'])
    TOKEN = payload['access_token']
    headers = {'Accept': 'application/json', 'Authorization': f"Bearer {TOKEN}"}
    response = requests.request("GET", CHAT_URL + '/models', headers=headers, data={})


@app.get("/auth")
async def auth():
    global TOKEN
    payload={'scope': 'GIGACHAT_API_PERS'}
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': RqUID,
        'Authorization': f'Basic {ATOKEN}'
    }
    response = requests.request("POST", AUTH_URL, headers=headers, data=payload)
    payload = json.loads(response.text)
    TOKEN = payload['access_token']
    return {"ok": True, "lifetime": payload["expires_at"]}


@app.post("/query")
async def query(req: QueryRequest):
    global GLOBAL_COUNTER
    GLOBAL_COUNTER += 1
    if GLOBAL_COUNTER == 10:
        auth()

    rag = state["rag"]
    _apply_generation_kwargs(rag, req.temperature, req.max_tokens)
    params = {
        "mode": req.mode,
        "system_prompt": req.system_prompt,
        "only_need_context": req.only_need_context,
        "top_k": req.top_k,
        "chunk_top_k": req.chunk_top_k,
        "response_type": req.response_type,
        "conversation_history": req.conversation_history,
        "user_prompt": req.user_prompt,
    }
    params = {k: v for k, v in params.items() if v is not None}
    try:
        answer = await rag.aquery(req.query, **params)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"query": req.query, "mode": req.mode, "answer": answer}



if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
    # "127.0.0.1:8000/docs"


