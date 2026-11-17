Готово. Изменения в `hvostun-core`:

1. **`compose.override.yml`** — добавлен сервис `rag` (локальный, как `db-ui`/`mailpit`):
   - собирается из `./rag`, образ `rag-server:latest`;
   - env берётся из `rag/env.local` (в образ не попадает — исключён `rag/.dockerignore`, а `load_dotenv` в контейнере просто ничего не находит и читает переменные окружения);
   - `./rag/rag_storage` примонтирован в `/app/rag_storage`;
   - healthcheck через `python urllib` — в slim-образе нет curl;
   - наружу не публикуется, доступен только внутри сети по `http://rag:8000`.

2. **`README.md`** — строка в таблице сервисов и команда запуска.

Почему в override, а не в `compose.yml`: деплой собирает стек как `compose.yml + compose.deploy.yml` и пинит по digest только backend. Сервис в `compose.yml` попал бы на прод, где `up -d` начал бы локально собирать образ с torch/mineru (несколько ГБ). Так локально работает, прод не трогает.

Запуск:

```bash
cd hvostun-core
docker compose up -d --build rag
docker compose ps rag
```

Отдельная копия в `workspace/rag` для стека не нужна — compose берёт `hvostun-core/rag`.
