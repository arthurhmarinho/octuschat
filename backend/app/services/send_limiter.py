"""Ponto de extensão para limitar envios por conta — AINDA NÃO LIMITA NADA.

Limites oficiais da Meta (Instagram API with Instagram Login):
- ~200 DMs automáticas por hora por conta;
- até 300 chamadas/s de envio de texto.

Como plugar um limitador de verdade no futuro (sem mudar o schema):
o worker chama `reserve(account_id)` antes de processar cada evento. Se
devolver um número de segundos, o evento volta para a fila com
`available_at = agora + atraso` (sem contar como tentativa). A contagem pode
usar a própria tabela `message_logs`/`messages` (envios da última hora por
conta) ou um contador em memória — sem Redis.

Atenção: um evento pode gerar vários envios (mensagem 1 + flow). Um limitador
real deve reservar pelo número de envios previstos, não por evento.
"""

from typing import Protocol


class SendLimiter(Protocol):
    async def reserve(self, account_id: str) -> float | None:
        """None = pode processar agora; float = segundos até poder."""


class NoLimit:
    """Implementação atual: nunca adia."""

    async def reserve(self, account_id: str) -> float | None:
        return None
