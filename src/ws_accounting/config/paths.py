"""XDG path resolution using platformdirs."""

from pathlib import Path

from platformdirs import user_config_dir, user_data_dir


APP_NAME = "ws-accounting"
APP_AUTHOR = "ws-accounting"


def get_config_dir() -> Path:
    """Return the user configuration directory for ws-accounting."""
    path = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    """Return the user data directory for ws-accounting."""
    path = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    """Return the path to the SQLite metadata database."""
    return get_data_dir() / "metadata.db"


def get_default_journal_dir() -> Path:
    """Return the default journal directory (~//finances)."""
    return Path.home() / "finances"


def get_config_file() -> Path:
    """Return the path to the TOML configuration file."""
    return get_config_dir() / "config.toml"


# Aliases used by app.py
database_path = get_db_path
default_journal_dir = get_default_journal_dir
