"""O token de convite não aparece no log de acesso."""

import logging

import pytest
from uvicorn.logging import AccessFormatter

import app.main  # noqa: F401  (instala o filtro)
from app.core.log_redaction import InviteTokenFilter, install, mask_invite_token

TOKEN = "Ab3_token-de-convite-que-nao-pode-vazar"


@pytest.mark.parametrize("path,expected", [
    (f"/auth/invites/{TOKEN}", "/auth/invites/***"),
    (f"/auth/invites/{TOKEN}/", "/auth/invites/***/"),
    (f"/auth/invites/{TOKEN}?x=1", "/auth/invites/***?x=1"),
    ("/auth/register", "/auth/register"),
    ("/admin/invites/7/renew", "/admin/invites/7/renew"),
    ("/health", "/health"),
])
def test_mascara_so_o_token(path, expected):
    assert mask_invite_token(path) == expected


def test_linha_do_log_de_acesso_sai_mascarada(monkeypatch):
    """Mesmo formato de registro e mesmo formatador que o uvicorn usa."""
    logger = logging.getLogger("uvicorn.access")
    # Os testes de migração rodam o Alembic neste processo, e o `fileConfig` dele
    # desliga os loggers já criados (em produção o Alembic é outro processo).
    monkeypatch.setattr(logger, "disabled", False)
    lines: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record):
            lines.append(self.format(record))

    handler = Capture()
    handler.setFormatter(AccessFormatter(
        '%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False))
    logger.addHandler(handler)
    level = logger.level
    logger.setLevel(logging.INFO)
    try:
        logger.info('%s - "%s %s HTTP/%s" %d',
                    "127.0.0.1:5000", "GET", f"/auth/invites/{TOKEN}", "1.1", 200)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)
    assert lines == ['127.0.0.1:5000 - "GET /auth/invites/*** HTTP/1.1" 200 OK']


def test_instalar_de_novo_nao_duplica():
    install()
    install()
    filters = logging.getLogger("uvicorn.access").filters
    assert sum(isinstance(f, InviteTokenFilter) for f in filters) == 1
