import pytest

from datagen.__main__ import main

SALT = "c" * 40


def test_cli_builds_database(tmp_path, capsys):
    assert main(["--accounts", "5", "--out", str(tmp_path / "a.db")]) == 0
    assert (tmp_path / "a.db").exists()


def test_cli_rejects_non_positive_accounts(tmp_path):
    assert main(["--accounts", "0", "--out", str(tmp_path / "a.db")]) == 2


def test_labels_require_salt_env(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("LABEL_SALT", raising=False)
    main(["--accounts", "5", "--out", str(tmp_path / "a.db")])
    code = main(["--out", str(tmp_path / "a.db"), "--labels-out", str(tmp_path / "l.json")])
    assert code == 2
    assert "LABEL_SALT" in capsys.readouterr().err


def test_labels_use_existing_database_without_rebuilding_it(tmp_path, monkeypatch):
    db = tmp_path / "a.db"
    assert main(["--accounts", "30", "--out", str(db)]) == 0
    before = db.read_bytes()
    monkeypatch.setenv("LABEL_SALT", SALT)
    out = tmp_path / "l.json"
    assert main(["--out", str(db), "--labels-out", str(out)]) == 0
    assert out.exists() and db.read_bytes() == before


def test_labels_fail_cleanly_when_database_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LABEL_SALT", SALT)
    code = main(["--out", str(tmp_path / "none.db"), "--labels-out", str(tmp_path / "l.json")])
    assert code == 2 and "not found" in capsys.readouterr().err


def test_weak_salt_exits_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LABEL_SALT", "short")
    main(["--accounts", "5", "--out", str(tmp_path / "a.db")])
    code = main(["--out", str(tmp_path / "a.db"), "--labels-out", str(tmp_path / "l.json")])
    assert code == 2
    assert "salt" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--seed", "--accounts"])
def test_cli_rejects_non_numeric(flag, tmp_path):
    with pytest.raises(SystemExit):
        main([flag, "abc", "--out", str(tmp_path / "a.db")])
