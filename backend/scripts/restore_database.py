"""Restore a target SQLite database into a clean path after schema validation."""

import argparse
import shutil
from pathlib import Path

from app.db import SCHEMA_VERSION, init_db, schema_tables


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    if args.target.exists():
        raise SystemExit(f"Refusing to overwrite existing target: {args.target}")
    args.target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.backup, args.target)
    try:
        version = init_db(args.target)
        required = {"farmers", "messages", "requests", "machines", "operators"}
        missing = required - schema_tables(args.target)
        if version != SCHEMA_VERSION or missing:
            raise RuntimeError(f"restore validation failed; missing={sorted(missing)}")
    except Exception:
        args.target.unlink(missing_ok=True)
        raise
    print(f"restored {args.target} at schema version {version}")


if __name__ == "__main__":
    main()
