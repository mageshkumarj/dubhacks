from pathlib import Path

import pytest

from datagen.writer import build_database

SEED = 7
ACCOUNTS = 300


@pytest.fixture(scope="session")
def sandbox_db(tmp_path_factory) -> Path:
    return build_database(tmp_path_factory.mktemp("sandbox") / "sandbox.db", seed=SEED, accounts=ACCOUNTS)
