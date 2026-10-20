Created pdf_rag_server.py. It imports build_rag/WORKING_DIR from lmstudio_pdf_rag.py, holds one RAGAnything for the process lifetime, and exposes:

- `GET` /health — status + whether ./rag_storage_pdf exists
- `POST` /build {"pdf_path": "..."} — parse + index a PDF
- `POST` /query {"query": "...", "mode": "hybrid", "system_prompt": "...", "temperature": 0.3, "max_tokens": 500, "top_k": 10, "chunk_top_k": 5, "only_need_context": false, "response_type": "Bullet Points", "conversation_history": [...], "user_prompt": "..."}

Run:
```python
pip install fastapi uvicorn
python pdf_rag_server.py            # http://127.0.0.1:8000
```

How the extra params map (this is the important part): 
- LightRAG has no per-query generation params — aquery kwargs go to QueryParam, which has no temperature/max_tokens. 
- So system_prompt is passed straight to aquery, while temperature/max_tokens are applied by rebuilding LightRAG's query role via update_llm_role_config("query", model_kwargs=...) (pdf_rag_server.py:77), only when they change. top_k/chunk_top_k are retrieval breadth, not sampling.


`/build` does not call finalize_storages() (that shuts down the LLM queues/storages and would break later queries); it's only called at shutdown.

Skipped: no streaming, auth, or per-request model/role switching (LightRAG rebuilds that wrapper, so it's not free). Couldn't run it — fastapi/uvicorn aren't installed in this env, and I couldn't exercise a live LM Studio; run it in your project venv to verify.

