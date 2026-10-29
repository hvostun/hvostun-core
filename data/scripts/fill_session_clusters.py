#!/usr/bin/env python3
"""Проставить survey_sessions.cluster по чипу собаки.

CSV: колонки animal_id, cluster. animal_id совпадает с dog_chips.code
целиком, с частью кода после последнего «_» (13_145222 → 145222)
или с тем же хвостом без ведущей A (A46931056 → 46931056).

Одинаковый animal_id с разными кластерами не записывается: в выводе
остаётся конфликт, сессии этой собаки не меняются.

Запуск из каталога backend:

    uv run python ../data/scripts/fill_session_clusters.py
    uv run python ../data/scripts/fill_session_clusters.py --dry-run
    uv run python ../data/scripts/fill_session_clusters.py --csv /path/to.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import uuid
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlmodel import Session, col, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.models import DogChip, SurveySession  # noqa: E402

_DEFAULT_CSV = (
    Path(__file__).resolve().parents[2].parent
    / "barko-docs"
    / "analytics"
    / "research_bohland_powell"
    / "datasets"
    / "unified"
    / "clusters_bohland_d10.csv"
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Заполнить cluster сессий по animal_id из CSV и dog_chips.code",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=_DEFAULT_CSV,
        help=f"CSV с колонками animal_id и cluster (по умолчанию {_DEFAULT_CSV})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать, что будет записано, без UPDATE",
    )
    return parser.parse_args(argv)


def load_clusters(path: Path) -> tuple[dict[str, str], list[str]]:
    """animal_id → cluster. Идентификаторы с разными кластерами исключаются."""
    if not path.is_file():
        raise SystemExit(f"CSV не найден: {path}")
    clusters: dict[str, str] = {}
    conflicts: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        if not {"animal_id", "cluster"} <= fields:
            raise SystemExit("В CSV нужны колонки animal_id и cluster")
        for line_no, row in enumerate(reader, start=2):
            animal_id = (row.get("animal_id") or "").strip()
            raw_cluster = (row.get("cluster") or "").strip()
            if not animal_id:
                raise SystemExit(f"Пустой animal_id, строка {line_no}")
            try:
                cluster = str(int(raw_cluster))
            except ValueError as exc:
                raise SystemExit(
                    f"Кластер не целое число, строка {line_no}: {raw_cluster!r}"
                ) from exc
            previous = clusters.get(animal_id)
            if previous is not None and previous != cluster:
                conflicts.add(animal_id)
            clusters[animal_id] = cluster
    for animal_id in conflicts:
        del clusters[animal_id]
    return clusters, sorted(conflicts)


def _lookup_keys(code: str) -> list[str]:
    text = code.strip()
    tail = text.rsplit("_", 1)[-1]
    keys = [text]
    if tail != text:
        keys.append(tail)
    if tail.startswith("A") and len(tail) > 1:
        keys.append(tail[1:])
    return keys


def cluster_for_code(code: str, clusters: dict[str, str]) -> str | None:
    """Кластер по коду чипа. Разные кластеры у кандидатов — нет совпадения."""
    found = {clusters[key] for key in _lookup_keys(code) if key in clusters}
    if len(found) == 1:
        return next(iter(found))
    return None


def matched_animal_id(code: str, clusters: dict[str, str]) -> str | None:
    cluster = cluster_for_code(code, clusters)
    if cluster is None:
        return None
    for key in _lookup_keys(code):
        if clusters.get(key) == cluster:
            return key
    return None


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    clusters, conflicts = load_clusters(args.csv)
    print(f"CSV: {args.csv}")
    print(f"Уникальных animal_id: {len(clusters)}; конфликтов: {len(conflicts)}")
    for animal_id in conflicts:
        print(f"  конфликт, пропуск: {animal_id}")

    updated = unchanged = 0
    with Session(engine) as db:
        chips = list(db.exec(select(DogChip)).all())
        by_dog: dict[uuid.UUID, str] = {}
        dog_conflict: set[uuid.UUID] = set()
        seen_animals: set[str] = set()
        for chip in chips:
            animal_id = matched_animal_id(chip.code, clusters)
            cluster = cluster_for_code(chip.code, clusters)
            if animal_id is None or cluster is None:
                continue
            seen_animals.add(animal_id)
            current = by_dog.get(chip.dog_id)
            if current is not None and current != cluster:
                dog_conflict.add(chip.dog_id)
                continue
            by_dog[chip.dog_id] = cluster
        for dog_id in dog_conflict:
            by_dog.pop(dog_id, None)
            print(f"  конфликт чипов одной собаки, пропуск dog_id={dog_id}")

        missing = sorted(set(clusters) - seen_animals)
        print(f"Чипов: {len(chips)}; собак с кластером: {len(by_dog)}")
        print(f"animal_id без чипа: {len(missing)}")
        for animal_id in missing:
            print(f"  нет в dog_chips: {animal_id}")

        if not by_dog:
            print("Нечего обновлять")
            return 0
        rows = list(
            db.exec(
                select(SurveySession).where(col(SurveySession.dog_id).in_(by_dog))
            ).all()
        )
        print(f"Сессий этих собак: {len(rows)}")
        for row in rows:
            cluster = by_dog[row.dog_id]
            if row.cluster == cluster:
                unchanged += 1
                continue
            print(f"  {row.id} dog={row.dog_id} {row.cluster!r} → {cluster}")
            if not args.dry_run:
                row.cluster = cluster
            updated += 1
        if args.dry_run:
            db.rollback()
            print(f"dry-run: обновилось бы {updated}, без изменений {unchanged}")
            return 0
        db.commit()
    print(f"Готово: обновлено {updated}, без изменений {unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
