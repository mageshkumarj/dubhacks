"""Read-only SQLite access. The API never writes to the dataset."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from .config import db_path


def connect(path: Path) -> sqlite3.Connection:
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    # One connection per request; it may cross threadpool threads, hence check_same_thread=False.
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = connect(db_path())
    try:
        yield conn
    finally:
        conn.close()
