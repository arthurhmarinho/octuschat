"""Mascara o token de convite no log de acesso do uvicorn.

`GET /auth/invites/{token}` leva o token no caminho, e o uvicorn registra o
caminho de cada requisição. Quem lê o log não pode sair com um link que ainda
vale.
"""

import logging
import re

_INVITE_PATH = re.compile(r"(/auth/invites/)[^/?\s]+")


def mask_invite_token(path: str) -> str:
    return _INVITE_PATH.sub(r"\1***", path)


class InviteTokenFilter(logging.Filter):
    """Reescreve o registro; nunca o descarta."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Argumentos do uvicorn.access: (cliente, método, caminho, versão, status).
        # São mantidos no lugar: o formatador dele depende dos cinco.
        if isinstance(record.args, tuple):
            record.args = tuple(
                mask_invite_token(a) if isinstance(a, str) else a for a in record.args
            )
        return True


def install() -> None:
    """Chamado ao importar o app: o uvicorn já configurou os loggers antes disso."""
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, InviteTokenFilter) for f in logger.filters):
        logger.addFilter(InviteTokenFilter())
