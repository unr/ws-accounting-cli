"""SQLite database connection manager and migration runner."""

import importlib
import sqlite3
from pathlib import Path


class Database:
    """Manages SQLite connection lifecycle and schema migrations."""

    def __init__(self, db_path: Path | str) -> None:
        """Initialize database. Use ':memory:' for testing."""
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def current_version(self) -> int:
        """Return current schema version (0 if no schema yet)."""
        try:
            row = self.conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            return row[0] if row and row[0] is not None else 0
        except sqlite3.OperationalError:
            return 0

    def migrate(self) -> None:
        """Run all pending migrations in order."""
        current = self.current_version()
        migrations_pkg = "ws_accounting.db.migrations"
        version = current + 1
        while True:
            module_name = f"{migrations_pkg}.{version:03d}_initial"
            try:
                mod = importlib.import_module(module_name)
            except ModuleNotFoundError:
                # Try without suffix for future migrations
                module_name = f"{migrations_pkg}.{version:03d}"
                try:
                    mod = importlib.import_module(module_name)
                except ModuleNotFoundError:
                    break
            mod.upgrade(self.conn)
            self.conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (version,),
            )
            self.conn.commit()
            version += 1
