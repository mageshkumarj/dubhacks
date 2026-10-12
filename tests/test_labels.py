import json
import sqlite3
from pathlib import Path

import pytest

from datagen.labels import ROOT, write_labels
from datagen.writer import build_database

SALT = "a" * 40
OTHER_SALT = "b" * 40


@pytest.fixture(scope="module")
def db(tmp_path_factory) -> Path:
    return build_database(tmp_path_factory.mktemp("lbl") / "s.db", seed=3, accounts=800)


def _labels(path: Path) -> dict:
    return json.loads(path.read_text())


def test_labels_are_deterministic_for_same_salt(tmp_path, db):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    write_labels(db, a, salt=SALT)
    write_labels(db, b, salt=SALT)
    assert a.read_text() == b.read_text()


def test_labels_change_with_salt(tmp_path, db):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    write_labels(db, a, salt=SALT)
    write_labels(db, b, salt=OTHER_SALT)
    assert a.read_text() != b.read_text()


def test_weak_salt_is_rejected(tmp_path, db):
    with pytest.raises(ValueError, match="salt"):
        write_labels(db, tmp_path / "x.json", salt="hackathon2026")


def test_labels_cover_all_accounts_with_realistic_churn_rate(tmp_path, db):
    out = tmp_path / "labels.json"
    write_labels(db, out, salt=SALT)
    labels = _labels(out)["churned_90d"]
    total = sqlite3.connect(db).execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    assert len(labels) == total
    assert 0.04 < sum(labels.values()) / total < 0.25


def test_reference_model_churn_is_predictable_from_signals(tmp_path, db):
    out = tmp_path / "labels.json"
    write_labels(db, out, salt=SALT)
    labels = _labels(out)["churned_90d"]
    rows = sqlite3.connect(db).execute("SELECT account_id, competitor_research_score FROM account_signals")
    rows = rows.fetchall()
    hi = [labels[a] for a, s in rows if s >= 0.6]
    lo = [labels[a] for a, s in rows if s < 0.3]
    assert sum(hi) / len(hi) > 2 * (sum(lo) / len(lo))


def test_output_never_embeds_model_parameters(tmp_path, db):
    out = tmp_path / "labels.json"
    write_labels(db, out, salt=SALT)
    payload = _labels(out)
    assert "params" not in payload
    assert payload["model"] == "reference"


def test_private_model_file_is_used_and_fingerprinted(tmp_path, db):
    model = tmp_path / "private_model.py"
    model.write_text("def probability(account_id, features, conn):\n    return 1.0\n")
    out = tmp_path / "labels.json"
    write_labels(db, out, salt=SALT, model_path=model)
    payload = _labels(out)
    assert set(payload["churned_90d"].values()) == {1}
    assert len(payload["model"]) == 64  # sha256 hex, not the code itself


def test_model_without_probability_function_is_rejected(tmp_path, db):
    model = tmp_path / "bad.py"
    model.write_text("x = 1\n")
    with pytest.raises(ValueError, match="probability"):
        write_labels(db, tmp_path / "o.json", salt=SALT, model_path=model)


def test_private_model_cannot_modify_the_dataset(tmp_path, db):
    model = tmp_path / "writes.py"
    model.write_text(
        "def probability(account_id, features, conn):\n"
        "    conn.execute('CREATE TABLE leaked_scores (account_id TEXT, score REAL)')\n"
        "    return 0.5\n"
    )
    with pytest.raises(sqlite3.OperationalError):
        write_labels(db, tmp_path / "o.json", salt=SALT, model_path=model)
    tables = {r[0] for r in sqlite3.connect(db).execute("SELECT name FROM sqlite_master")}
    assert "leaked_scores" not in tables


def test_refuses_to_write_inside_repo_outside_private(db):
    with pytest.raises(ValueError, match="private"):
        write_labels(db, ROOT / "data" / "labels_holdout.json", salt=SALT)
