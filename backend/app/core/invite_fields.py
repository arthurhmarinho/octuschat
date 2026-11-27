"""Normalização e validação dos campos digitados em convites e no cadastro."""

import re

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_IG_RE = re.compile(r"[a-z0-9._]{1,30}")


class InvalidField(ValueError):
    """A mensagem vai direto para a tela."""


def clean_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise InvalidField("Informe o nome")
    return name


def clean_email(email: str) -> str:
    email = email.strip().lower()
    if not _EMAIL_RE.fullmatch(email):
        raise InvalidField("E-mail inválido")
    return email


def clean_ig_username(value: str) -> str:
    """Aceita `@Fulano` e devolve `fulano`."""
    value = value.strip().removeprefix("@").lower()
    if not _IG_RE.fullmatch(value):
        raise InvalidField(
            "@ do Instagram inválido: use letras, números, ponto e sublinhado (até 30)"
        )
    return value
