import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import config


SCHEMA_VERSION = 6
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


@contextmanager
def connect(path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    database_path = Path(path or config.DB_PATH).expanduser()
    if not database_path.is_absolute():
        database_path = Path(__file__).resolve().parents[1] / database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def migrate(path: str | Path | None = None) -> int:
    """Apply numbered migrations transactionally to the target database."""
    with connect(path) as connection:
        current = connection.execute("PRAGMA user_version").fetchone()[0]
        files = _migration_files()
        if current > len(files):
            raise RuntimeError(f"Unsupported database schema version: {current}")
        for version, migration in enumerate(files, start=1):
            if version <= current:
                continue
            connection.execute('BEGIN IMMEDIATE')
            statement = ''
            for line in migration.read_text(encoding='utf-8').splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    connection.execute(statement)
                    statement = ''
            if statement.strip():
                raise RuntimeError(f'Incomplete migration: {migration.name}')
            connection.execute(f"PRAGMA user_version={version}")
            connection.commit()
        return len(files)


def init_db(path: str | Path | None = None) -> int:
    version = migrate(path)
    from .catalog import install_catalog
    with connect(path) as db:
        install_catalog(db)
    return version


def schema_tables(path: str | Path) -> set[str]:
    with connect(path) as connection:
        return {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }


def backup_database(path: str | Path, backup_path: str | Path | None = None) -> Path:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination = (
        Path(backup_path).expanduser().resolve()
        if backup_path
        else source.with_name(f"{source.name}.backup")
    )
    if destination.exists():
        raise FileExistsError(destination)
    with sqlite3.connect(source) as original, sqlite3.connect(destination) as backup:
        original.backup(backup)
    return destination


def database_path():
    return Path(config.resolve_db_path(config.DB_PATH))

def log_database_error(exc, stage="database.transaction"):
    from .diagnostics import event
    event(stage, outcome="error", exception_type=type(exc).__name__,
          sqlite_error_code=getattr(exc, "sqlite_errorcode", None))
