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
    GET  /health -> server + storage status
    GET  /auth   -> refresh the GigaChat access token
    POST /query  -> question against the index, or the same LLM without RAG

POST /query mode:
    hybrid | local | global | mix | naive  retrieval + answer (default hybrid)
    bypass                                 same GigaChat, no retrieval (baseline)

In bypass only query, system_prompt and conversation_history are sent to the LLM.
top_k, chunk_top_k, only_need_context, response_type and user_prompt are ignored.
temperature and max_tokens are accepted but not applied in any mode.
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import numpy as np
import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from lightrag.llm.openai import openai_complete_if_cache
from openai import (
    OpenAI,  # Убедитесь, что импорт корректен
    RateLimitError,  # Убедитесь, что импорт корректен
)
from pydantic import BaseModel, ConfigDict, Field

# RAG-Anything imports
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

# GigaChat TLS: НУЦ Минцифры is not in Mozilla/certifi.
# Same file as backend: repo certs/russian_trusted_root_ca_pem.crt → /certs in Compose.
_GIGACHAT_CA = os.environ.get(
    "GIGACHAT_CA_BUNDLE", "/certs/russian_trusted_root_ca_pem.crt"
)
_SSL_VERIFY: bool | str = True
if os.path.isfile(_GIGACHAT_CA):
    try:
        import certifi

        _merged = "/tmp/rag_ca_bundle.pem"
        certifi_pem = Path(certifi.where()).read_text(encoding="utf-8").strip() + "\n"
        russian_pem = Path(_GIGACHAT_CA).read_text(encoding="utf-8").strip() + "\n"
        Path(_merged).write_text(certifi_pem + russian_pem, encoding="utf-8")
        os.environ["SSL_CERT_FILE"] = _merged
        os.environ["REQUESTS_CA_BUNDLE"] = _merged
        os.environ["CURL_CA_BUNDLE"] = _merged
        _SSL_VERIFY = _merged
    except Exception:  # noqa: BLE001
        _SSL_VERIFY = _GIGACHAT_CA


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
def _ensure_gigachat_token(*, force: bool = False) -> str:
    """GigaChat access token for openai-compatible client (and OPENAI_API_KEY fallback)."""
    global TOKEN, GLOBAL_COUNTER
    if force or not TOKEN:
        authh()
    else:
        GLOBAL_COUNTER += 1
        if GLOBAL_COUNTER >= 10:
            authh()
    assert TOKEN is not None
    # lightrag/openai falls back to env when api_key is missing
    os.environ["OPENAI_API_KEY"] = TOKEN
    return TOKEN


async def llm_model_func(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list[dict] = None,  # noqa RUF013
    **kwargs,
) -> str:
    # history_messages: list[dict] = None, RUF013 PEP 484 prohibits implicit `Optional`
    api_key = _ensure_gigachat_token()

    # GigaChat rejects these OpenAI-oriented kwargs from LightRAG.
    kwargs.pop("response_format", None)
    kwargs.pop("keyword_extraction", None)

    return await openai_complete_if_cache(
        model=CHAT_MODEL,
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages or [],
        base_url=CHAT_URL,
        api_key=api_key,
        **kwargs,
    )


state: dict[str, Any] = {"rag": None, "gen_kwargs": {}}


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
    """One body for both RAG and no-RAG (`mode=bypass`) so the same JSON can be compared."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "Как приучить щенка к поводку?",
                    "mode": "hybrid",
                    "system_prompt": "Please answer in Russian and format your response as a bulleted list.",
                },
                {
                    "query": "Как приучить щенка к поводку?",
                    "mode": "bypass",
                    "system_prompt": "Please answer in Russian and format your response as a bulleted list.",
                },
            ]
        }
    )

    query: str = Field(description="Текст вопроса.")
    mode: Literal["hybrid", "local", "global", "mix", "naive", "bypass"] = Field(
        "hybrid",
        description=(
            "Режим LightRAG. \nhybrid, local, global, mix, naive — ответ по индексу. "
            "\nbypass — тот же GigaChat без retrieval (baseline). "
            "\nВ bypass учитываются только query, system_prompt и conversation_history."
        ),
    )
    system_prompt: str | None = Field(
        None,
        description="Системная инструкция. Учитывается и в RAG, и в bypass.",
    )
    temperature: float | None = Field(
        None,
        description="Не применяется: прокидывание в LightRAG закомментировано (и RAG, и bypass).",
    )
    max_tokens: int | None = Field(
        None,
        description="Не применяется: прокидывание в LightRAG закомментировано (и RAG, и bypass).",
    )
    top_k: int | None = Field(
        None,
        description="Ширина retrieval (сущности или связи). В bypass игнорируется.",
    )
    chunk_top_k: int | None = Field(
        None,
        description="Сколько текстовых чанков оставить после retrieval. В bypass игнорируется.",
    )
    only_need_context: bool = Field(
        False,
        description="Вернуть найденный контекст вместо ответа. В bypass игнорируется.",
    )
    response_type: str | None = Field(
        None,
        description='Формат ответа RAG, например "Bullet Points". В bypass игнорируется.',
    )
    conversation_history: list[dict[str, Any]] | None = Field(
        None,
        description=(
            'История [{"role", "content"}]. Учитывается и в RAG, и в bypass. '
            "Пример Swagger без role/content отбрасывается."
        ),
    )
    user_prompt: str | None = Field(
        None,
        description="Дополнительные инструкции в промпт RAG. В bypass игнорируются.",
    )


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
    # ✅ Прямое использование атрибута query_llm_model_kwargs llm_model_kwargs
    # ✅ Use the generic `llm_model_kwargs` attribute
    merged = dict(rag.lightrag.llm_model_kwargs or {})
    # rag.lightrag.role_llm_kwargs.get("query")
    # merged = dict(rag.lightrag._get_effective_role_llm_kwargs("query") or rag.lightrag.llm_model_kwargs or {})
    merged.update(gen)
    rag.lightrag.aupdate_llm_role_config(
        "query", provider_options={"temperature": temperature, "max_tokens": max_tokens}
    )
    # rag.lightrag.update_llm_role_config("query", model_kwargs=merged)
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


def authh():
    global TOKEN
    global GLOBAL_COUNTER
    GLOBAL_COUNTER = 0
    if not ATOKEN.strip() or not RqUID.strip():
        raise HTTPException(
            503,
            "RqUID and ATOKEN must be set in rag/env.local (GigaChat Studio)",
        )
    payload = {"scope": "GIGACHAT_API_PERS"}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": RqUID,
        "Authorization": f"Basic {ATOKEN}",
    }
    try:
        response = requests.post(
            AUTH_URL,
            headers=headers,
            data=payload,
            timeout=30,
            verify=_SSL_VERIFY,
        )
    except requests.exceptions.SSLError as exc:
        raise HTTPException(
            502,
            "GigaChat TLS failed (НУЦ Минцифры). Mount repo certs/ or set GIGACHAT_CA_BUNDLE.",
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise HTTPException(502, f"GigaChat auth unreachable: {exc}") from exc
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(
            502, f"GigaChat auth non-JSON ({response.status_code}): {response.text[:200]}"
        ) from exc
    if response.status_code != 200 or "access_token" not in body:
        raise HTTPException(
            502,
            f"GigaChat auth failed ({response.status_code}): {body}",
        )
    print(body.get("expires_at"))
    TOKEN = body["access_token"]
    os.environ["OPENAI_API_KEY"] = TOKEN
    return body.get("expires_at")


@app.get("/auth")
async def auth():
    exp = authh()
    return {"ok": True, "lifetime": exp}


@app.post(
    "/query",
    summary="Вопрос с RAG или без (mode=bypass)",
    description=(
        "hybrid, local, global, mix, naive — ответ по индексу LightRAG. "
        "mode=bypass — тот же GigaChat (CHAT_MODEL) без retrieval: "
        "учитываются query, system_prompt и conversation_history; "
        "top_k, chunk_top_k, only_need_context, response_type и user_prompt игнорируются. "
        "temperature и max_tokens сейчас не применяются ни в одном режиме."
    ),
)
async def query(req: QueryRequest):
    _ensure_gigachat_token()

    rag = state["rag"]
    # await _apply_generation_kwargs(rag, req.temperature, req.max_tokens)
    history = req.conversation_history
    if history and not all(
        isinstance(m, dict) and "role" in m and "content" in m for m in history
    ):
        # Swagger default `[{additionalProp1:{}}]` breaks LightRAG; ignore it.
        history = None
    params = {
        "mode": req.mode,
        "system_prompt": req.system_prompt,
        "only_need_context": req.only_need_context,
        "top_k": req.top_k,
        "chunk_top_k": req.chunk_top_k,
        "response_type": req.response_type,
        "conversation_history": history,
        "user_prompt": req.user_prompt,
    }
    params = {k: v for k, v in params.items() if v is not None}
    try:
        answer = await rag.aquery(req.query, **params)
    except Exception as e:  # noqa BLE001
        raise HTTPException(500, str(e)) from e
    if answer is None:
        raise HTTPException(
            502,
            "RAG returned empty answer (LLM failed). Check logs for OPENAI_API_KEY / GigaChat.",
        )
    return {"query": req.query, "mode": req.mode, "answer": answer}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
    # "127.0.0.1:8000/docs"
