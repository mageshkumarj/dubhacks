import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_VERSION = "0.1.0"


def db_path() -> Path:
    return Path(os.environ.get("SANDBOX_DB", ROOT / "data" / "sandbox.db"))
