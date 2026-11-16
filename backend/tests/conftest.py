import pytest
from cryptography.fernet import Fernet

from app.core.config import settings


@pytest.fixture
def fernet_key(monkeypatch) -> str:
    """Configura TOKEN_ENCRYPTION_KEYS com uma chave nova para o teste."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "token_encryption_keys", key)
    return key
