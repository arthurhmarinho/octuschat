"""Configurações da aplicação, lidas do ambiente (.env em dev)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False
    )

    # ── App ──────────────────────────────────────────────
    app_name: str = "InboxPilot API"
    environment: str = "development"  # development | production
    frontend_url: str = "http://localhost:3000"

    # ── Banco (Supabase Postgres) ────────────────────────
    # Formato async: postgresql+psycopg://USER:PASS@HOST:PORT/DB
    # Use a connection string do *pooler* do Supabase.
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/inboxpilot"
    db_echo: bool = False

    # ── Meta / Instagram Graph API ───────────────────────
    meta_app_id: str = ""
    meta_app_secret: str = ""
    webhook_verify_token: str = "troque-este-valor"
    oauth_redirect_uri: str = "http://localhost:8000/instagram/callback"
    graph_api_version: str = "v21.0"
    # Permite desligar temporariamente a checagem de assinatura (debug).
    webhook_enforce_signature: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
