# hvostun-core

Реализация продукта **Hvostun**: backend, frontend и ML-пакет в одном репозитории.

## Архитектура

**Modular monolith:** один backend, один frontend, один `docker compose up`.

Bootstrap: [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template).

```text
hvostun-core/
  compose.yml
  backend/
    app/
      api/routes/
      admin/             # domain admin
      ml-plan/           # ingest, export, baseline K3
      llm-chat/          # LLM client, RAG, prompt/safety policies
      alembic/
    notebooks/
    pyproject.toml
  frontend/
    src/
  data/
    parquet/             # open subsets / K3 export
    kb/                  # curated knowledge base для RAG (llm-chat)
```

| Сервис Compose | Роль |
|----------------|------|
| `backend` | FastAPI + SQLModel + Alembic + auth/API |
| `db` | PostgreSQL — единственная OLTP |
| `redis` | sessions/cache; Celery broker позже |
| frontend | React build, обслуживается backend (не отдельный prod-контейнер) |
| `jupyter` | опционально; тот же `app.ml_plan` и БД |
| `worker` | Celery — когда появится фоновая задача |

## Стек

| Слой | Выбор |
|------|--------|
| Backend | FastAPI, Pydantic, SQLModel/SQLAlchemy, Alembic |
| Auth | JWT из шаблона; `is_superuser` + `shelter_memberships` |
| API | OpenAPI + generated frontend client |
| UI | React, TypeScript, Tailwind, shadcn/ui |
| Admin | dashboard шаблона; spike FastAdmin для domain CRUD |
| ML | scikit-learn tabular (`RandomForest` + `LogisticRegression`); lockfile `uv.lock` |
| Deploy | Compose: `backend` + `db` + `redis` |
