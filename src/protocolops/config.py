from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from protocolops.paths import find_repo_root, resolve_path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    mock: bool = Field(default=True, validation_alias="PROTOCOLOPS_MOCK")
    site_url: str = Field(default="https://docs.helios.example/", validation_alias="PROTOCOLOPS_SITE_URL")
    docs_path: str = Field(default="fixtures/docs", validation_alias="PROTOCOLOPS_DOCS_PATH")
    docs_url: str | None = Field(default=None, validation_alias="PROTOCOLOPS_DOCS_URL")
    output_dir: str = Field(default="output", validation_alias="PROTOCOLOPS_OUTPUT_DIR")
    fixtures_dir: str = Field(default="fixtures", validation_alias="PROTOCOLOPS_FIXTURES_DIR")
    brand: str = Field(default="Helios Protocol", validation_alias="PROTOCOLOPS_BRAND")
    draft_count: int = Field(default=3, validation_alias="PROTOCOLOPS_DRAFT_COUNT")

    gsc_oauth_client_file: str | None = Field(default=None, validation_alias="GSC_OAUTH_CLIENT_FILE")
    gsc_token_file: str = Field(default=".protocolops/token.json", validation_alias="GSC_TOKEN_FILE")
    google_application_credentials: str | None = Field(
        default=None, validation_alias="GOOGLE_APPLICATION_CREDENTIALS"
    )

    ga4_enabled: bool = Field(default=False, validation_alias="PROTOCOLOPS_GA4")
    ga4_property_id: str | None = Field(default=None, validation_alias="GA4_PROPERTY_ID")

    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")

    desk_host: str = Field(default="127.0.0.1", validation_alias="PROTOCOLOPS_DESK_HOST")
    desk_port: int = Field(default=8787, validation_alias="PROTOCOLOPS_DESK_PORT")

    @property
    def root(self) -> Path:
        return find_repo_root()

    def docs_dir(self) -> Path:
        return resolve_path(self.docs_path, root=self.root)

    def out_dir(self) -> Path:
        return resolve_path(self.output_dir, root=self.root)

    def fixture_dir(self) -> Path:
        return resolve_path(self.fixtures_dir, root=self.root)

    def token_path(self) -> Path:
        return resolve_path(self.gsc_token_file, root=self.root)

    def oauth_client_path(self) -> Path | None:
        if not self.gsc_oauth_client_file:
            return None
        return resolve_path(self.gsc_oauth_client_file, root=self.root)

    def service_account_path(self) -> Path | None:
        if not self.google_application_credentials:
            return None
        return resolve_path(self.google_application_credentials, root=self.root)

    def has_google_credentials(self) -> bool:
        sa = self.service_account_path()
        oauth = self.oauth_client_path()
        token = self.token_path()
        return bool((sa and sa.is_file()) or (oauth and oauth.is_file()) or token.is_file())

    def use_mock_gsc(self) -> bool:
        return self.mock or not self.has_google_credentials()


def load_settings(**overrides: object) -> Settings:
    settings = Settings()
    if overrides:
        settings = settings.model_copy(update=overrides)
    return settings
