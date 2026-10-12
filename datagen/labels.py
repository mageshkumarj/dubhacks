"""Held-out outcome labels, generated separately and never written into the public dataset.

The judging model is a private Python file exposing
`probability(account_id: str, features: dict, conn: sqlite3.Connection) -> float`.
It may query `conn` for any extra signal. Without a private model the toy reference model is used.
"""

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path
from types import ModuleType

from . import catalog, reference_model
from .util import derived_rng

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_DIR = ROOT / "private"
MIN_SALT_LENGTH = 32
SUPPORT_WINDOW_DAYS = 90

_FEATURES_SQL = f"""

SELECT a.account_id AS account_id, a.tenure_months AS tenure_months,
  s.competitor_research_score AS competitor_research, s.port_out_inquiry AS port_out_inquiry,
  (SELECT COUNT(*) FROM support_interactions i WHERE i.account_id = a.account_id
     AND i.interaction_date >= date(:as_of, '-{SUPPORT_WINDOW_DAYS} day')) AS support_90d,
  (SELECT COALESCE(AVG(sentiment), 0) FROM support_interactions i
     WHERE i.account_id = a.account_id) AS avg_sentiment,
  (SELECT total_cents FROM billing_history b WHERE b.account_id = a.account_id
     ORDER BY month DESC LIMIT 1) AS last_bill,
  (SELECT AVG(total_cents) FROM billing_history b WHERE b.account_id = a.account_id
     AND month < (SELECT MAX(month) FROM billing_history c WHERE c.account_id = a.account_id)) AS prior_bill,
  (SELECT COALESCE(AVG(CASE WHEN (p.data_cap_gb IS NOT NULL AND u.g > p.data_cap_gb)
                          OR (p.tier = 'premium' AND u.g < 5) THEN 1.0 ELSE 0.0 END), 0)
     FROM lines l JOIN plans p ON p.sku = l.plan_sku
     JOIN (SELECT line_id, AVG(data_gb) g FROM usage_monthly GROUP BY line_id) u USING (line_id)
     WHERE l.account_id = a.account_id) AS plan_misfit_share
FROM accounts a JOIN account_signals s USING (account_id) ORDER BY a.account_id
"""


def _check_output_location(out_path: Path) -> None:
    resolved = out_path.resolve()
    inside_repo = ROOT in resolved.parents
    if inside_repo and PRIVATE_DIR not in resolved.parents:
        raise ValueError(f"Refusing to write labels inside the repo; use {PRIVATE_DIR} or a path outside it.")


def _check_salt(salt: str) -> None:
    if len(salt) < MIN_SALT_LENGTH:
        raise ValueError(
            f"salt must be at least {MIN_SALT_LENGTH} characters. "
            'Generate one: python -c "import secrets; print(secrets.token_hex(32))"'
        )


def _load_model(model_path: Path | None) -> tuple[ModuleType, str]:
    if model_path is None:
        return reference_model, "reference"
    source = Path(model_path).read_bytes()
    spec = importlib.util.spec_from_file_location("private_label_model", model_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "probability", None)):
        raise ValueError("model file must define probability(account_id, features, conn)")
    return module, hashlib.sha256(source).hexdigest()


def _features(row: sqlite3.Row) -> dict:
    data = dict(row)
    prior = data.pop("prior_bill")
    last = data.pop("last_bill")
    data["bill_increase_pct"] = max(0.0, last / prior - 1) if prior else 0.0
    return data


def write_labels(db_path: Path, out_path: Path, salt: str, model_path: Path | None = None) -> Path:
    out_path = Path(out_path)
    _check_salt(salt)
    _check_output_location(out_path)
    model, fingerprint = _load_model(model_path)
    conn = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(_FEATURES_SQL, {"as_of": catalog.AS_OF.isoformat()}).fetchall()
        churned = {}
        for row in rows:
            account_id = row["account_id"]
            p = model.probability(account_id, _features(row), conn)
            churned[account_id] = int(derived_rng(salt, account_id).random() < p)
    finally:
        conn.close()
    payload = {"as_of": catalog.AS_OF.isoformat(), "model": fingerprint, "churned_90d": churned}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, sort_keys=True, indent=1))
    return out_path
