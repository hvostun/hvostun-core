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

from rag_builder import build_rag
import uvicorn

import requests

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from dotenv import load_dotenv


TOKEN = None 

load_dotenv('env.local')

CHAT_URL = os.environ["CHAT_URL"] 
AUTH_URL = os.environ["AUTH_URL"]
EMBED_URL = os.environ["EMBED_URL"]

RqUID = os.environ["RqUID"]
ATOKEN = os.environ["ATOKEN"]
EMBED_TOKEN = os.environ["EMBED_TOKEN"]


state: Dict[str, Any] = {"rag": None, "gen_kwargs": {}}


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     rag = build_rag()
#     await rag._ensure_lightrag_initialized()
#     state["rag"] = rag
#     print(f"✅ RAG ready (working_dir={WORKING_DIR})")
#     try:
#         yield
#     finally:
#         await rag.finalize_storages()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_SIZE = 15 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {"application/docx", "application/txt", "application/pdf"}


app = FastAPI(title="LM Studio PDF RAG") #, lifespan=lifespan)


class BuildRequest(BaseModel):
    pdf_path: str = Field(description="Path to a PDF on the server machine")


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
    return {"ok": True}
    # return {
    #     "ok": state["rag"] is not None,
    #     "working_dir": WORKING_DIR,
    #     "storage_exists": os.path.isdir(WORKING_DIR),
    # }


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


@app.get("/chat_models")
async def chat_models():
    headers = {'Accept': 'application/json', 'Authorization': f"Bearer {TOKEN}"}
    response = requests.request("GET", CHAT_URL + '/models', headers=headers, data={})
    return {"ok": True, "responce": json.loads(response.text)}


# @app.get("/embed_models")
# async def embed_models():
#     headers = {'Accept': 'application/json', 'Authorization': }
#     response = requests.request("GET", url + '/models', headers=headers, data={})
#     return {"ok": True, "responce": json.loads(response.text)}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # maybe maybe 
    # Проверка MIME-типа
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый тип файла: {file.content_type}",
        )
    # Читаем содержимое и проверяем размер
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    # Генерируем безопасное имя
    suffix = Path(file.filename).suffix
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOAD_DIR / safe_name
    # Сохраняем
    with dest.open("wb") as buffer:
        buffer.write(contents)
    return {"filename": safe_name, "size": len(contents)}

# @app.post("/build")
# async def build(req: BuildRequest):
#     if not os.path.isfile(req.pdf_path):
#         raise HTTPException(404, f"File not found: {req.pdf_path}")
#     rag = state["rag"]
#     await rag.process_document_complete(
#         file_path=req.pdf_path,
#         output_dir=OUTPUT_DIR,
#         parse_method="auto",
#         display_stats=True,
#     )
#     return {"ok": True, "file": req.pdf_path}


# @app.post("/query")
# async def query(req: QueryRequest):
#     rag = state["rag"]
#     _apply_generation_kwargs(rag, req.temperature, req.max_tokens)
#     params = {
#         "mode": req.mode,
#         "system_prompt": req.system_prompt,
#         "only_need_context": req.only_need_context,
#         "top_k": req.top_k,
#         "chunk_top_k": req.chunk_top_k,
#         "response_type": req.response_type,
#         "conversation_history": req.conversation_history,
#         "user_prompt": req.user_prompt,
#     }
#     params = {k: v for k, v in params.items() if v is not None}
#     try:
#         answer = await rag.aquery(req.query, **params)
#     except Exception as e:
#         raise HTTPException(500, str(e))
#     return {"query": req.query, "mode": req.mode, "answer": answer}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
