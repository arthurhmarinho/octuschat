"""Ponto de extensão para limitar envios por conta — AINDA NÃO LIMITA NADA.

Limites documentados pela Meta (Instagram API with Instagram Login):
- 750 private replies por hora, por conta;
- 300 envios por segundo de mensagens de texto (Send API).
Os "~200 DMs/hora" que circulam por aí vêm de blogs, não da doc oficial.

Como funciona: antes de enviar qualquer coisa de um evento, o engine chama
`reserve(account_id, sends=N, private_replies=P)` com o número de envios
previstos (mensagens do flow que serão enviadas agora; P = 1 quando a
primeira é private reply). Se devolver segundos, o engine levanta
`SendDeferred` ANTES de enviar qualquer coisa, e o worker devolve o evento à
fila com `available_at = agora + atraso`, sem contar como tentativa.

Um limitador real pode contar os envios da última hora por conta na própria
tabela `messages`/`message_logs`, ou num contador em memória — sem Redis.
"""

from typing import Protocol


class SendDeferred(Exception):
    """O limitador mandou esperar: o evento volta para a fila sem enviar nada."""

    def __init__(self, delay: float):
        self.delay = delay
        super().__init__(f"envio adiado {delay:.0f}s pelo limitador da conta")


class SendLimiter(Protocol):
    async def reserve(
        self, account_id: str, sends: int = 1, private_replies: int = 0
    ) -> float | None:
        """None = pode enviar agora; float = segundos até poder."""


class NoLimit:
    """Implementação atual: nunca adia."""

    async def reserve(
        self, account_id: str, sends: int = 1, private_replies: int = 0
    ) -> float | None:
        return None
