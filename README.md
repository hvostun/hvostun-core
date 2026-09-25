# hvostun-core

Реализация продукта **Hvostun**. Текущий runtime — backend и HTML-админка.
`frontend/` хранится только как заготовка будущего пользовательского интерфейса.

## Архитектура

**Modular monolith:** один backend, один `docker compose up`. Админка — Jinja +
Bootstrap в `backend/app/admin`. `frontend/` не собирается, не запускается, не
деплоится и не имеет активной интеграции с backend. Продуктового JSON API
сейчас нет: backend отдаёт только HTML-админку и `GET /health`.

Bootstrap проекта: [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template).

```text
hvostun-core/
  compose.yml
  backend/
    app/
      admin/             # Jinja + Bootstrap, единственный UI
      ml-plan/           # ingest, export, baseline K3
      llm-chat/          # LLM client, RAG, prompt/safety policies
      alembic/
    notebooks/
    pyproject.toml
  frontend/              # неактивная React-заготовка будущего user UI
  data/
    parquet/             # open subsets / K3 export
    kb/                  # curated knowledge base для RAG (llm-chat)
```

| Сервис Compose | Роль |
|----------------|------|
| `db` | PostgreSQL 18 — OLTP `hvostun_{FASTAPI_ENV}` (local: `hvostun_development`) |
| `backend` | FastAPI: HTML-админка + `GET /health` |
| `db-ui` / `proxy` / `mailpit` | вспомогательные local-сервисы; `db-ui` — образ Adminer, не продуктовая админка |
| `redis` / `jupyter` / `worker` | позже, в Compose сейчас нет |

Проверка стека: скопировать `.env.example` → `.env`, затем `docker compose up -d db backend`.

## Стек

| Слой | Выбор |
|------|--------|
| Backend | FastAPI, Pydantic, SQLModel/SQLAlchemy, Alembic |
| Auth | JWT cookie для HTML-админки; `is_superuser` + `group` |
| API | нет; OpenAPI/Swagger отключены. Проверка живости — `GET /health` |
| Admin UI | Jinja2 + Bootstrap в `backend/app/admin` |
| Web UI | Не реализован; `frontend/` — неподключённая заготовка |
| DB UI | Adminer (`db-ui`), только local |
| ML | scikit-learn tabular (`RandomForest` + `LogisticRegression`); lockfile `uv.lock` |
| Deploy | `compose.yml` + `compose.deploy.yml`: HTTPS `proxy` + `backend` + `db`; `db-ui` отключён |

bash scripts/db_backup.sh

docker compose exec -T db psql -U postgres -d hvostun_development < .data/backup/hvostun_development.sql