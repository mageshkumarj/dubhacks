import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_IGNORES = {"private/", ".venv/", "__pycache__/", "*.pyc", ".pytest_cache/", ".ruff_cache/", ".coverage",
                    "htmlcov/", "*.db.tmp", ".DS_Store"}


def test_gitignore_protects_private_and_local_files():
    entries = {line.strip() for line in (ROOT / ".gitignore").read_text().splitlines()}
    assert REQUIRED_IGNORES <= entries
    assert "data/sandbox.db" not in entries and "*.db" not in entries


def _git(*args: str, check: bool = True) -> str:
    # fixed git arguments against this checkout, no user input
    return subprocess.run(  # noqa: S603
        [shutil.which("git"), *args], cwd=ROOT, capture_output=True, text=True, check=check
    ).stdout.strip()


@pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs a git checkout")
def test_prepublish_checks_pass_on_a_clean_repo():
    assert _git("ls-files", "private/") == ""
    assert _git("grep", "-lE", r'"churned_90d": \{$', check=False) == ""


def test_readme_documents_the_working_prepublish_checks():
    readme = (ROOT / "README.md").read_text()
    assert "xargs grep -l churned_90d" not in readme
    assert "git ls-files private/" in readme
