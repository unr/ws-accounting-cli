"""XDG-compliant path resolution using platformdirs."""

from pathlib import Path

from platformdirs import user_config_dir, user_data_dir


APP_NAME = "ws-accounting"

_config_dir = Path(user_config_dir(APP_NAME))
_data_dir = Path(user_data_dir(APP_NAME))


def config_dir() -> Path:
    """Return the app config directory, creating it if needed."""
    _config_dir.mkdir(parents=True, exist_ok=True)
    return _config_dir


def data_dir() -> Path:
    """Return the app data directory, creating it if needed."""
    _data_dir.mkdir(parents=True, exist_ok=True)
    return _data_dir


def config_file() -> Path:
    """Return the path to the main config file (TOML)."""
    return config_dir() / "config.toml"


def database_path() -> Path:
    """Return the path to the SQLite sidecar database."""
    return data_dir() / "metadata.db"


def default_journal_dir() -> Path:
    """Return the default journal directory (~//finances/)."""
    return Path.home() / "finances"


def package_data_dir() -> Path:
    """Return the path to bundled package data (default accounts, sample journals, rules)."""
    return Path(__file__).parent.parent / "data"
