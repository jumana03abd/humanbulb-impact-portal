from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .config import get_settings


@contextmanager
def get_db() -> Iterator[psycopg.Connection]:
    settings = get_settings()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return list(cur.fetchall())


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        conn.commit()


def execute_returning(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        record = cur.fetchone()
        conn.commit()
        if record is None:
            raise RuntimeError("Expected database record but none was returned.")
        return record
