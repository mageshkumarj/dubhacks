import sqlite3
from pathlib import Path

import pytest

from datagen.writer import build_database, content_checksum

SHIPPED = Path(__file__).resolve().parent.parent / "data" / "sandbox.db"
pytestmark = pytest.mark.skipif(not SHIPPED.exists(), reason="data/sandbox.db is not present")


def _metadata(path: Path) -> tuple[dict[str, str], str]:
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return dict(conn.execute("SELECT key, value FROM metadata")), content_checksum(conn)
    finally:
        conn.close()


def test_shipped_checksum_matches_its_rows():
    meta, actual = _metadata(SHIPPED)
    assert meta["content_sha256"] == actual, "data/sandbox.db was edited after it was generated"


def test_shipped_database_matches_the_generator(tmp_path):
    shipped, _ = _metadata(SHIPPED)
    rebuilt, _ = _metadata(build_database(tmp_path / "rebuilt.db", seed=int(shipped["seed"]), accounts=5000))
    assert rebuilt["content_sha256"] == shipped["content_sha256"], (
        "generator changed but data/sandbox.db was not regenerated"
    )
