#!/usr/bin/env python3
"""Generate GigaChat expert narratives for survey sessions in a loop.

Models come from dictionary ``gigachat::models`` (see admin → Справочники),
with ``GIGACHAT_MODEL`` as the default and always included. The script walks
sessions and assigns models round-robin.

Run from the ``backend`` directory:

    uv run python scripts/generate_summaries.py
    uv run python scripts/generate_summaries.py --limit 20 --sleep 1
    uv run python scripts/generate_summaries.py --force
    uv run python scripts/generate_summaries.py --model GigaChat-2-Max
    uv run python scripts/generate_summaries.py --session-id <uuid>
    docker compose exec backend uv run python scripts/generate_summaries.py
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from collections.abc import Iterable

from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.db import engine
from app.models import SurveySession, User
from app.services import dictionaries as dictionary_service
from app.services import sessions as session_service
from app.services import summary as summary_service


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Сгенерировать рассказы для эксперта (GigaChat) по сессиям",
    )
    parser.add_argument(
        "--session-id",
        action="append",
        default=[],
        metavar="UUID",
        help="Только эта сессия (можно указать несколько раз)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Максимум сессий (0 = все)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Перегенерировать даже при свежем fingerprint",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Пауза между запросами к GigaChat, секунды (по умолчанию 0.5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только список сессий и моделей, без вызовов GigaChat",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Только сессии без сохранённого summary (игнорирует --force)",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Одна модель для всех сессий (иначе round-robin по справочнику)",
    )
    return parser.parse_args(argv)


def _actor(session: Session) -> User:
    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if user is None:
        user = session.exec(select(User).where(col(User.is_superuser).is_(True))).first()
    if user is None:
        raise SystemExit("Нет пользователя для generated_by (superuser)")
    return user


def _session_ids(
    session: Session,
    *,
    explicit: list[str],
    limit: int,
    only_missing: bool,
) -> list[uuid.UUID]:
    if explicit:
        ids: list[uuid.UUID] = []
        for raw in explicit:
            try:
                ids.append(uuid.UUID(raw))
            except ValueError as exc:
                raise SystemExit(f"Некорректный --session-id: {raw}") from exc
        return ids

    statement = select(SurveySession.id).order_by(col(SurveySession.created_at).asc())
    if only_missing:
        statement = statement.where(col(SurveySession.summary).is_(None))
    if limit > 0:
        statement = statement.limit(limit)
    return list(session.exec(statement).all())


def _models_for_run(session: Session, pinned: str) -> list[str]:
    available = dictionary_service.list_gigachat_models(session)
    if not available:
        raise SystemExit(
            "Нет моделей: задайте GIGACHAT_MODEL или справочник gigachat::models"
        )
    chosen = pinned.strip()
    if not chosen:
        return available
    if chosen not in available:
        raise SystemExit(
            f"Модель {chosen!r} нет в справочнике/дефолте. Доступны: {', '.join(available)}"
        )
    return [chosen]


def _run(
    ids: Iterable[uuid.UUID],
    args: argparse.Namespace,
    models: list[str],
) -> int:
    ok = skipped = errors = 0
    with Session(engine) as db:
        actor = _actor(db)
        id_list = list(ids)
        total = len(id_list)
        print(
            f"Сессий: {total}; модели (по кругу): {', '.join(models)}; "
            f"force={args.force}; dry_run={args.dry_run}"
        )
        for index, session_id in enumerate(id_list, start=1):
            model = models[(index - 1) % len(models)]
            prefix = f"[{index}/{total}] {session_id} model={model}"
            if args.dry_run:
                print(f"{prefix} dry-run")
                skipped += 1
                continue
            try:
                context = session_service.get_session_context(db, session_id, actor)
            except session_service.SessionNotFoundError as exc:
                print(f"{prefix} error: {exc}")
                errors += 1
                continue
            if args.only_missing and context.row.summary is not None:
                print(f"{prefix} skipped: summary уже есть")
                skipped += 1
                continue
            outcome = summary_service.generate_and_store_summary(
                db,
                context,
                generated_by=actor.id,
                force=args.force and not args.only_missing,
                model=model,
            )
            if outcome.status == "ok":
                ok += 1
                preview = (outcome.stored.narrative[:80] + "…") if outcome.stored else ""
                print(f"{prefix} ok: {preview}")
            elif outcome.status == "skipped":
                skipped += 1
                print(f"{prefix} skipped: {outcome.detail}")
            else:
                errors += 1
                print(f"{prefix} error: {outcome.detail}")
            if args.sleep > 0 and index < total:
                time.sleep(args.sleep)
    print(f"Готово: ok={ok} skipped={skipped} errors={errors}")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not settings.gigachat_enabled and not args.dry_run:
        print("GigaChat не настроен (нет GIGACHAT_AUTH_KEY)", file=sys.stderr)
        return 2
    with Session(engine) as db:
        ids = _session_ids(
            db,
            explicit=args.session_id,
            limit=args.limit,
            only_missing=args.only_missing,
        )
        models = _models_for_run(db, args.model)
    return _run(ids, args, models)


if __name__ == "__main__":
    raise SystemExit(main())
