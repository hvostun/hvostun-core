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

Старт.

```
cd backend/
docker compose build
docker compose up -d
docker compose logs backend -f --tail=10
```

```
cd backend/
uv run pytest
```

Проверки перед коммитом. Из корня репозитория:

```bash
uv run prek run --all-files
```

Команда гоняет все хуки из `.pre-commit-config.yaml` по всему дереву, не только по изменённым файлам. Один хук можно повторить так: `uv run prek run local-mypy --all-files`. Имя хука — строка `id` в конфиге.

В отчёте у каждого хука есть имя и итог. `Passed` значит, что проверка прошла. `Failed` значит, что ниже будет код выхода и текст ошибки. Путь в ошибке читается как `файл:строка`.

Что делать с типичным отказом:

| Хук | Что сломалось | Как разобрать |
|-----|----------------|---------------|
| `end-of-file-fixer`, `trailing-whitespace` | нет перевода строки в конце файла или висят пробелы | хук уже поправил файл. Посмотрите `git diff` и запустите команду ещё раз |
| `local-ruff-check` | стиль и ошибки ruff | ruff часто правит сам. Если после правки код всё ещё красный, в выводе будет код правила (`F401`, `I001`) и строка. Правьте её и повторите `uv run prek run local-ruff-check --all-files` |
| `local-ruff-format` | формат не как у ruff | хук переписывает файл. Сверьте diff и запустите ещё раз |
| `local-mypy`, `local-ty` | типы | строка вида `файл:строка: error: … [код]`. Исправьте тип в этом месте и повторите соответствующий хук |
| `typos` | слово похоже на опечатку | сообщение `слово` should be `исправление` и место в файле. Если это опечатка — замените. Если написание намеренное (код справочника, имя колонки), добавьте его в `[tool.typos.default.extend-words]` в корневом `pyproject.toml` |
| `local-pip-audit` | известная уязвимость в зависимости | в выводе пакет и версия. Обновите пакет в `backend/pyproject.toml` и `uv.lock` |
| `check-added-large-files`, `check-toml`, `check-yaml` | слишком большой файл или сломанный toml/yaml | в выводе путь файла. Уменьшите файл или поправьте синтаксис |

Хуки идут дальше, даже если один уже упал. Чините по списку `Failed` сверху вниз и запускайте проверку снова, пока все строки не станут `Passed`.

http://localhost:8000/ - экспертный контур
http://localhost:8080/ - бд

Миграции

```
alembic upgrade head
```

Сделать бэкап

```bash
bash scripts/db_backup.sh
```

Раскатить бэкап
```bash
docker compose exec -T db psql -U postgres -d hvostun_development < .data/backup/hvostun_development.sql
```
