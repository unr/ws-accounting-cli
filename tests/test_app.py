"""Smoke tests for the main application."""

from ws_accounting.app import WSAccountingApp
from ws_accounting.config.paths import package_data_dir


def test_app_instantiates():
    """The app can be created without errors."""
    app = WSAccountingApp()
    assert app.title == "ws-accounting"


def test_package_data_exists():
    """Bundled data files are accessible."""
    data = package_data_dir()
    assert (data / "default_accounts.journal").exists()
    assert (data / "sample_journal.journal").exists()
    assert (data / "sample_rules" / "generic.rules").exists()
