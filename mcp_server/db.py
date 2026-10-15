"""Connections to the shop database.

Two rules live here rather than in every tool:

* Tools talk to the **working copy** (`data/campus_customs_new.db`), never to
  the pristine original. `./scripts/reset_db.sh` restores the working copy.
* Read tools open the file **read-only**, so a SELECT-only tool cannot write by
  accident. Tools that spend money or resolve a ticket pass `readonly=False`.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "campus_customs_new.db"


def db_path() -> Path:
    """The working copy. `CAMPUS_CUSTOMS_DB` overrides it for tests."""
    return Path(os.environ.get("CAMPUS_CUSTOMS_DB", DEFAULT_DB_PATH))


@contextmanager
def connect(readonly: bool = True) -> Iterator[sqlite3.Connection]:
    """Open the working copy with rows that behave like dicts."""
    path = db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"database not found at {path} — run ./scripts/reset_db.sh to create "
            "the working copy from the original"
        )

    uri = f"file:{path}?mode=ro" if readonly else f"file:{path}"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        if not readonly:
            conn.commit()
    except Exception:
        if not readonly:
            conn.rollback()
        raise
    finally:
        conn.close()


def rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None
