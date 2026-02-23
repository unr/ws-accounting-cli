"""Application configuration with TOML persistence."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

from ws_accounting.config.paths import config_file, default_journal_dir


class AIConfig(BaseModel):
    """AI provider settings."""

    api_key: str = ""
    model: str = "claude-sonnet-4-5-20250929"
    enabled: bool = True
    max_tokens_per_request: int = 4096


class ImportConfig(BaseModel):
    """CSV import settings."""

    default_status: str = "*"
    rules_dir: str = ""


class AppConfig(BaseModel):
    """Top-level application configuration."""

    journal_path: str = ""
    data_dir: str = ""
    currency: str = "$"
    fiscal_year_start: int = 1
    theme: str = "financial-dark"
    compact_mode: bool = False
    first_run: bool = True
    ai: AIConfig = Field(default_factory=AIConfig)
    import_config: ImportConfig = Field(default_factory=ImportConfig)

    @classmethod
    def load(cls) -> AppConfig:
        """Load config from TOML file, or return defaults."""
        path = config_file()
        if path.exists():
            with open(path, "rb") as f:
                data = tomllib.load(f)
            return cls.model_validate(data)
        return cls()

    def save(self) -> None:
        """Save config to TOML file."""
        path = config_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_toml(path, self.model_dump())


def _toml_value(value: object) -> str:
    """Format a Python value as a TOML value string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return str(value)


def _write_toml(path: Path, data: dict) -> None:
    """Write a dict as TOML. Handles flat values + one level of nesting."""
    lines: list[str] = []
    tables: list[tuple[str, dict]] = []

    for key, value in data.items():
        if isinstance(value, dict):
            tables.append((key, value))
        else:
            lines.append(f"{key} = {_toml_value(value)}")

    for section, values in tables:
        lines.append("")
        lines.append(f"[{section}]")
        for key, value in values.items():
            if not isinstance(value, dict):
                lines.append(f"{key} = {_toml_value(value)}")

    path.write_text("\n".join(lines) + "\n")
