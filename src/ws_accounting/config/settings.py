"""Application configuration with TOML persistence."""

from pathlib import Path

from pydantic import BaseModel, Field

from ws_accounting.config.paths import get_config_file, get_default_journal_dir


class AIConfig(BaseModel):
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    enabled: bool = True
    max_tokens: int = 4096


class ImportConfig(BaseModel):
    default_status: str = "*"
    rules_dir: str = ""


class AppConfig(BaseModel):
    journal_dir: Path = Field(default_factory=get_default_journal_dir)
    currency: str = "$"
    fiscal_year_start: int = 1  # month number
    theme: str = "financial-dark"
    ai: AIConfig = Field(default_factory=AIConfig)
    import_config: ImportConfig = Field(default_factory=ImportConfig)
    compact_mode: bool = False
    first_run: bool = True

    @classmethod
    def load(cls) -> "AppConfig":
        """Load config from TOML file, creating defaults if missing."""
        config_file = get_config_file()
        if config_file.exists():
            import tomllib

            with open(config_file, "rb") as f:
                data = tomllib.load(f)
            return cls.model_validate(data)
        return cls()

    def save(self) -> None:
        """Save config to TOML file."""
        config_file = get_config_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        lines.append(f'journal_dir = "{self.journal_dir}"')
        lines.append(f'currency = "{self.currency}"')
        lines.append(f"fiscal_year_start = {self.fiscal_year_start}")
        lines.append(f'theme = "{self.theme}"')
        lines.append(f"compact_mode = {'true' if self.compact_mode else 'false'}")
        lines.append(f"first_run = {'true' if self.first_run else 'false'}")
        lines.append("")
        lines.append("[ai]")
        lines.append(f'api_key = "{self.ai.api_key}"')
        lines.append(f'model = "{self.ai.model}"')
        lines.append(f"enabled = {'true' if self.ai.enabled else 'false'}")
        lines.append(f"max_tokens = {self.ai.max_tokens}")
        lines.append("")
        lines.append("[import_config]")
        lines.append(f'default_status = "{self.import_config.default_status}"')
        lines.append(f'rules_dir = "{self.import_config.rules_dir}"')
        config_file.write_text("\n".join(lines) + "\n")
