# hvostun-core

Реализация продукта **Hvostun**. Текущий runtime — backend с HTML-админкой и
собранное приложение `frontend/` на поддомене `profile`.

## Архитектура

**Modular monolith:** один backend, один `docker compose up`. Админка — Jinja +
Bootstrap в `backend/app/admin`. `frontend/` — собранное SPA на React в
отдельном контейнере, без API и без доступа к backend. Продуктового JSON API
сейчас нет: backend отдаёт только HTML-админку и `GET /health`. Данные
экранов profile пока живут в `localStorage` браузера.

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
  frontend/              # SPA profile: исходники, тесты, справочник design/
  data/
    parquet/             # open subsets / K3 export
    kb/                  # curated knowledge base для RAG (llm-chat)
```

| Сервис Compose | Роль |
|----------------|------|
| `db` | PostgreSQL 18 — OLTP `hvostun_{FASTAPI_ENV}` (local: `hvostun_development`) |
| `backend` | FastAPI: HTML-админка + `GET /health` |
| `frontend` | nginx: собранное SPA `profile`, только сеть `profile` |
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
| Web UI | SPA `frontend/` на `PROFILE_DOMAIN`; до OTP вход — Basic Auth nginx и формальный экран S2 |
| DB UI | Adminer (`db-ui`), только local |
| ML | scikit-learn tabular (`RandomForest` + `LogisticRegression`); lockfile `uv.lock` |
| Deploy | `compose.yml` + `compose.deploy.yml`: HTTPS `proxy` + `backend` + `frontend` + `db`; `db-ui` отключён |

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
http://profile.localhost/ - приложение profile
http://localhost:8080/ - бд

## Frontend (profile)

В образ попадает только собранный `dist` SPA (React, TypeScript, Vite). nginx
отдаёт его с фолбэком на `index.html`. Справочник дизайна — `frontend/design/`
(макеты, дизайн-система, handoff, иллюстрации); в образ из него входят только
иллюстрации, которые импортирует приложение. Шрифты Onest, Oswald и Neucha
приходят из npm, в CSP внешних доменов нет.

Локально, из каталога `frontend/`:

```bash
npm ci
npm run dev
npm test
npm run test:e2e
npm run build
```

Пока нет серверного API, экраны читают `LocalApi`: данные одного браузера в
`localStorage`. Это расходится с handoff, где вход и данные серверные.
Участник пилота не продолжит анкету на другом устройстве. Экран входа S2
формальный: любой непустой логин и пароль при отмеченном согласии; настоящий
барьер — Basic Auth nginx. С появлением OTP его заменит `src/api/http.ts`.

Локально сайт открывается как `http://profile.localhost`: Chrome и Firefox
резолвят `*.localhost` в 127.0.0.1. Для curl нужен заголовок хоста:

```bash
curl -H 'Host: profile.localhost' http://127.0.0.1/
```

Пока нет входа по почте, nginx спрашивает один логин и пароль из
`PROFILE_LOGIN` и `PROFILE_PASSWORD`. В `.env.example` стоят заглушки.
Настоящие значения только в локальном `.env`, в `.env` на сервере и в GitHub
Secrets. Пароль, который уже светился в переписке, нужно сменить перед
публичным пилотом.

В проде Traefik выпускает отдельный сертификат для `PROFILE_DOMAIN`
(`profile.hvostun.com`). Образ задаётся digest-переменной `FRONTEND_IMAGE`
(`ghcr.io/hvostun/hvostun-frontend@sha256:...`).

Сети Docker:

- `public` (`hvostun_public`) — только proxy, порты 80 и 443;
- `admin` (`hvostun_admin`, internal) — proxy и backend;
- `profile` (`hvostun_profile`, internal) — proxy и frontend;
- `db` (`hvostun_db`, internal) — backend, prestart, db, db-roles;
- `egress` (`hvostun_egress`) — backend и локальный mailpit, исходящие вызовы;
- `socket` (`hvostun_socket`, internal) — proxy и socket-proxy.

Frontend не входит в сети backend и БД. Backend не входит в сеть frontend.

Проверка изоляции:

```bash
docker compose exec frontend wget -q -T 3 -O- http://backend:8000/health
docker compose exec frontend wget -q -T 3 -O- http://db:5432
docker compose exec frontend wget -q -T 3 -O- https://example.com
docker compose exec backend python -c "import urllib.request as u; u.urlopen('http://frontend:8080/healthz', timeout=3)"

set -a; . ./.env; set +a
auth="${PROFILE_LOGIN}:${PROFILE_PASSWORD}"
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: profile.localhost' http://127.0.0.1/
curl -s -o /dev/null -w '%{http_code}\n' -u "$auth" -H 'Host: profile.localhost' http://127.0.0.1/
curl -s -o /dev/null -w '%{http_code}\n' -u "$auth" -H 'Host: profile.localhost' http://127.0.0.1/login
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: localhost' http://127.0.0.1/chat
```

Ожидание: первые четыре команды завершаются ошибкой, дальше коды `401`, `200`,
`200`, `404`. `200` на `/login` — экран SPA. `404` на `Host: localhost` `/chat`
приходит от backend, не от profile.

Первый выкат:

1. DNS: A (и AAAA, если есть IPv6) для `profile.hvostun.com` на IP сервера.
2. На сервере в `.env` (права 600): `PROFILE_DOMAIN=profile.hvostun.com`, `PROFILE_LOGIN`, `PROFILE_PASSWORD`.
3. В GitHub: `vars.PROFILE_DOMAIN`, secrets `PROFILE_LOGIN` и `PROFILE_PASSWORD`.
4. Предупредить пользователей админки: после выката сессия сбросится, нужно войти заново.
5. Мёрж в `main`. При первом выкате Docker пересоздаёт сети, простой около минуты. Бэкап БД делает `scripts/deploy.sh` до этого.
6. Пройти проверку изоляции на сервере.

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
