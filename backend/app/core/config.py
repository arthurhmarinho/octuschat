"""Configurações da aplicação, lidas do ambiente (.env em dev)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False
    )

    # ── App ──────────────────────────────────────────────
    app_name: str = "Octus Chat API"
    environment: str = "development"  # development | production
    frontend_url: str = "http://localhost:3000"

    # ── Autenticação da API ──────────────────────────────
    # Segredo compartilhado com o proxy do Next (BACKEND_API_SECRET no front).
    # Vazio = a API recusa todas as rotas protegidas (falha fechada).
    api_secret: str = ""

    # ── Criptografia dos tokens da Meta (Fernet) ─────────
    # Uma ou mais chaves separadas por vírgula. A 1ª cifra; todas decifram
    # (permite rotação). Gere com:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_keys: str = ""

    # ── Banco (Supabase Postgres) ────────────────────────
    # Formato async: postgresql+psycopg://USER:PASS@HOST:PORT/DB
    # Use a connection string do *pooler* do Supabase.
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/inboxpilot"
    db_echo: bool = False
    # Opcional: URL usada só pelas migrações (Alembic). No Supabase, use a do
    # *session pooler* (porta 5432) — DDL no transaction pooler é frágil.
    migrations_database_url: str = ""

    # ── Meta / Instagram Graph API ───────────────────────
    meta_app_id: str = ""
    meta_app_secret: str = ""
    webhook_verify_token: str = "troque-este-valor"
    oauth_redirect_uri: str = "http://localhost:8000/instagram/callback"
    graph_api_version: str = "v21.0"

    # ── Worker da fila de webhooks ───────────────────────
    # true = roda como task no próprio servidor web (padrão).
    # false = não roda aqui (ex.: se virar um processo/serviço separado).
    webhook_worker_enabled: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
