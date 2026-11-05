import argparse
import json
import sqlite3
from pathlib import Path

from app.db import backup_database, init_db


TABLES = (
    "farmers",
    "messages",
    "requests",
    "conversations",
    "conversation_turns",
    "machines",
    "bookings",
    "catalog_terms",
    "dialogue_audit",
    "dialogue_outgoing",
    "dialogue_context",
    "dialogue_drafts",
    "dialogue_sessions",
    "dialogue_confirmations",
    "employment_drafts",
    "employment_listings",
)


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in connection.execute(f'PRAGMA table_info("{table}")')
    }


def import_legacy(source: Path, target: Path, *, dry_run: bool) -> dict[str, int]:
    if source.resolve() == target.resolve():
        raise ValueError("Source and target databases must be different")
    if not source.is_file():
        raise FileNotFoundError(source)
    if target.exists() and not dry_run:
        backup_database(target)
    init_db(target)
    counts: dict[str, int] = {}
    source_connection = sqlite3.connect(source)
    source_connection.row_factory = sqlite3.Row
    try:
        with sqlite3.connect(target) as target_connection:
            target_connection.execute("PRAGMA foreign_keys=OFF")
            for table in TABLES:
                source_tables = {
                    row[0]
                    for row in source_connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if table not in source_tables:
                    continue
                source_columns = _columns(source_connection, table)
                target_columns = _columns(target_connection, table)
                columns = sorted(source_columns & target_columns)
                if not columns:
                    continue
                rows = source_connection.execute(
                    f'SELECT {", ".join(columns)} FROM "{table}"'
                ).fetchall()
                counts[table] = len(rows)
                if dry_run:
                    continue
                placeholders = ", ".join("?" for _ in columns)
                target_connection.executemany(
                    f'INSERT OR IGNORE INTO "{table}" ({", ".join(columns)}) '
                    f"VALUES ({placeholders})",
                    [tuple(row[column] for column in columns) for row in rows],
                )
            target_connection.commit()
    finally:
        source_connection.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import legacy records into a fresh integrated database."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    counts = import_legacy(args.source, args.target, dry_run=args.dry_run)
    print(json.dumps({"dry_run": args.dry_run, "tables": counts}, sort_keys=True))


if __name__ == "__main__":
    main()
