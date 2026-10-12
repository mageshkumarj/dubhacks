"""CLI: python -m datagen [--seed N] [--accounts N] [--out PATH]

Organizer-only (uses the existing --out dataset read-only):
  LABEL_SALT=<secret> python -m datagen --labels-out private/labels.json [--label-model private/model.py]
"""

import argparse
import os
import sys
from pathlib import Path

from .labels import write_labels
from .writer import DEFAULT_ACCOUNTS, DEFAULT_SEED, build_database

DEFAULT_OUT = Path("data/sandbox.db")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="datagen", description="Generate the stub sandbox dataset.")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--accounts", type=int, default=DEFAULT_ACCOUNTS)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--labels-out", type=Path, help="Write held-out labels here (organizers only).")
    p.add_argument("--label-model", type=Path, help="Private Python file defining probability().")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.accounts < 1:
        print("--accounts must be >= 1", file=sys.stderr)
        return 2
    salt = os.environ.get("LABEL_SALT", "")
    if args.labels_out and not salt:
        print("Set the LABEL_SALT environment variable (never pass secrets as arguments).", file=sys.stderr)
        return 2
    if args.labels_out:
        return _write_labels(args, salt)
    db = build_database(args.out, seed=args.seed, accounts=args.accounts)
    print(f"wrote {db} (seed={args.seed}, accounts={args.accounts})")
    return 0


def _write_labels(args: argparse.Namespace, salt: str) -> int:
    """Labels are computed from an EXISTING dataset, which is never rebuilt or modified."""
    if not args.out.exists():
        print(f"error: dataset not found at {args.out}; generate it first", file=sys.stderr)
        return 2
    try:
        print(f"wrote {write_labels(args.out, args.labels_out, salt, args.label_model)}")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
