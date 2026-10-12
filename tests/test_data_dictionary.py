"""The data dictionary must describe the real schema and the real values. This test fails when they drift."""

import re
import sqlite3
from pathlib import Path

import pytest

from datagen.writer import SCHEMA, build_database

DICTIONARY = Path(__file__).resolve().parent.parent / "docs" / "data-dictionary.md"
CATEGORICAL = {
    "accounts": ("segment", "credit_tier", "contact_preference", "language", "discount_group"),
    "lines": ("member_role",),
    "support_interactions": ("channel", "topic"),
    "devices": ("tier", "status", "manufacturer"),
    "plans": ("tier", "family", "variant", "status", "eligibility"),
    "addons": ("kind", "per"),
    "promotions": ("kind", "per", "source"),
    "personas": ("kind", "primary_theme", "stated_usage"),
    "billing_history": ("change_reason",),
}


@pytest.fixture(scope="module")
def text() -> str:
    return DICTIONARY.read_text()


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    db = build_database(tmp_path_factory.mktemp("doc") / "d.db", seed=11, accounts=300)
    connection = sqlite3.connect(db)
    yield connection
    connection.close()


def schema_tables() -> dict[str, list[str]]:
    tables = {}
    for statement in SCHEMA.read_text().split(";"):
        match = re.search(r"CREATE TABLE (\w+)\s*\(", statement)
        if not match:
            continue
        body = statement[match.end(): statement.rindex(")")].replace("\n", " ")
        columns = []
        for part in re.split(r",\s*(?![^()]*\))", body):
            word = part.strip().split(" ")[0]
            if word and word.upper() not in {"PRIMARY", "FOREIGN", "UNIQUE"}:
                columns.append(word)
        tables[match.group(1)] = columns
    return tables


def section(text: str, table: str) -> str:
    """The dictionary bullet (and its indented sub-bullets) that documents a table."""
    blocks = re.split(r"\n(?=- |## )", text)
    return "\n".join(b for b in blocks if re.match(rf"- `{table}\b", b) or f"`{table}(" in b or f"`{table}`" in b)


@pytest.mark.parametrize("table", sorted(schema_tables()))
def test_every_table_is_documented(text, table):
    assert section(text, table), f"table {table} is not in docs/data-dictionary.md"


@pytest.mark.parametrize("table,columns", sorted(schema_tables().items()))
def test_every_column_is_documented(text, table, columns):
    block = section(text, table)
    missing = [c for c in columns if not re.search(rf"(?<![\w]){re.escape(c)}(?![\w])", block)]
    assert missing == [], f"{table}: undocumented columns {missing}"


def test_every_metadata_key_is_documented(text, conn):
    keys = [r[0] for r in conn.execute("SELECT key FROM metadata")]
    assert [k for k in keys if f"`{k}`" not in text] == []


def test_current_schema_version_is_stated(text, conn):
    version = conn.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()[0]
    assert f"Current schema version: **{version}**" in text


@pytest.mark.parametrize("table,columns", sorted(CATEGORICAL.items()))
def test_every_category_value_in_the_data_is_listed(text, conn, table, columns):
    block = section(text, table)
    for column in columns:
        values = [r[0] for r in conn.execute(f"SELECT DISTINCT {column} FROM {table}") if r[0]]  # noqa: S608
        missing = [v for v in values if str(v) not in block]
        assert missing == [], f"{table}.{column}: values not in the dictionary: {missing}"
