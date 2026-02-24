"""SQLite connection manager and migration runner."""

import sqlite3
from importlib import import_module
from pathlib import Path


class Database:
    """SQLite connection manager with automatic migration support."""

    def __init__(self, db_path: Path | str) -> None:
        """Initialize database.

        Args:
            db_path: Path to SQLite file, or ':memory:' for testing.
        """
        self.db_path = db_path if isinstance(db_path, Path) else Path(db_path) if db_path != ":memory:" else db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Open or return existing connection."""
        if self._conn is None:
            if isinstance(self.db_path, Path):
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def migrate(self) -> None:
        """Run all pending migrations."""
        conn = self.connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT DEFAULT (datetime('now'))
            )
        """)
        current = self._current_version(conn)
        # Discover and run migrations
        migration_num = current + 1
        while True:
            # Try with suffix first (e.g., 001_initial), then bare number
            module_name = f"ws_accounting.db.migrations.{migration_num:03d}_initial"
            try:
                mod = import_module(module_name)
            except ImportError:
                module_name = f"ws_accounting.db.migrations.{migration_num:03d}"
                try:
                    mod = import_module(module_name)
                except ImportError:
                    break
            mod.upgrade(conn)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (migration_num,),
            )
            conn.commit()
            migration_num += 1

    def _current_version(self, conn: sqlite3.Connection) -> int:
        """Return the current schema version (0 if none applied)."""
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] or 0 if row else 0

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
