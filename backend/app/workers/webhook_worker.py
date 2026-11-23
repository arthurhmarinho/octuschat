"""Worker da fila de webhooks (tabela `webhook_events`), sem Redis.

Onde roda: por padrão, como task asyncio no lifespan do FastAPI (mesmo
processo do servidor — ver app/main.py). Também roda sozinho, como processo
separado, se um dia valer a pena (ex.: Background Worker no Render):

    python -m app.workers.webhook_worker

(nesse caso, defina WEBHOOK_WORKER_ENABLED=false no serviço web.)

Concorrência: `claim_batch` usa SELECT … FOR UPDATE SKIP LOCKED, então várias
instâncias/processos podem rodar juntos sem pegar o mesmo evento.

Tentativas: o engine já trata falhas de envio (grava em message_logs); o que
chega aqui como exceção é erro inesperado (banco, decifrar token…). Nesses
casos o evento volta para a fila com backoff, até MAX_ATTEMPTS. Um evento que
falhou no meio pode ter enviado parte do flow; a mensagem 1 tem idempotência
(message_logs), os passos seguintes não — por isso poucas tentativas.

Rate limit: o engine reserva no limitador os envios previstos do evento
antes de enviar; se ele mandar esperar (`SendDeferred`), o evento volta à
fila sem contar tentativa.
"""

import asyncio
import logging
import time
from datetime import timedelta

from app.core.database import SessionLocal
from app.core.security import redact_secrets
from app.crud import webhook_event as queue
from app.services import token_service
from app.services.send_limiter import NoLimit, SendDeferred, SendLimiter
from app.services.webhook_events import dispatch

logger = logging.getLogger("inboxpilot.worker")

MAX_ATTEMPTS = 3
# Atraso antes da 2ª e da 3ª tentativa.
RETRY_DELAYS = (timedelta(seconds=30), timedelta(minutes=2))
STALE_AFTER = timedelta(minutes=5)
KEEP_DONE_FOR = timedelta(days=14)
POLL_INTERVAL = 2.0  # segundos ociosos entre consultas (o webhook acorda antes)
BATCH_SIZE = 10
REQUEUE_EVERY = 60.0  # segundos
PURGE_EVERY = 3600.0  # segundos
RENEW_EVERY = 12 * 3600.0  # segundos: renovação proativa dos tokens da Meta


def retry_delay(attempts: int) -> timedelta:
    """Atraso para a próxima tentativa, dado quantas já foram feitas."""
    return RETRY_DELAYS[min(attempts, len(RETRY_DELAYS)) - 1]


class WebhookWorker:
    def __init__(
        self,
        session_factory=SessionLocal,
        limiter: SendLimiter | None = None,
        batch_size: int = BATCH_SIZE,
        poll_interval: float = POLL_INTERVAL,
    ):
        self._session_factory = session_factory
        self._limiter = limiter or NoLimit()
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._wake = asyncio.Event()
        self._stopping = False
        self._last_requeue = 0.0
        self._last_purge = 0.0
        # None = ainda não rodou: a 1ª passagem renova na hora (ao subir o servidor).
        self._last_renew: float | None = None

    def notify(self) -> None:
        """Acorda o worker na hora (chamado pelo endpoint após enfileirar)."""
        self._wake.set()

    async def stop(self) -> None:
        self._stopping = True
        self._wake.set()

    async def run(self) -> None:
        """Loop principal. Nunca morre por erro: loga e tenta de novo."""
        logger.info("Worker de webhooks iniciado.")
        while not self._stopping:
            try:
                await self.maintenance()
                processed = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Erro no loop do worker; tentando de novo.")
                processed = 0
            if processed == 0 and not self._stopping:
                await self._idle()
        logger.info("Worker de webhooks parado.")

    async def _idle(self) -> None:
        self._wake.clear()
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=self._poll_interval)
        except TimeoutError:
            pass

    async def run_once(self) -> int:
        """Reserva um lote e processa em ordem. Devolve quantos pegou."""
        async with self._session_factory() as db:
            events = await queue.claim_batch(db, self._batch_size)
        for event in events:
            await self._process(event)
        return len(events)

    async def _process(self, event) -> None:
        started = time.monotonic()
        try:
            async with self._session_factory() as db:
                await dispatch(
                    db, event.kind, event.account_id, event.payload, limiter=self._limiter
                )
        except SendDeferred as deferred:
            # O engine reservou os envios previstos e o limitador mandou
            # esperar — nada foi enviado. Volta à fila sem contar tentativa.
            async with self._session_factory() as db:
                await queue.defer(db, event.id, timedelta(seconds=deferred.delay))
            logger.info(
                "Evento %s adiado %.0fs (limite da conta).", event.id, deferred.delay
            )
            return
        except Exception as exc:  # noqa: BLE001
            error = redact_secrets(f"{type(exc).__name__}: {exc}")[:2000]
            async with self._session_factory() as db:
                if event.attempts >= MAX_ATTEMPTS:
                    await queue.mark_failed(db, event.id, error)
                    logger.exception(
                        "Evento %s falhou de vez (%s tentativas).", event.id, event.attempts
                    )
                else:
                    delay = retry_delay(event.attempts)
                    await queue.mark_retry(db, event.id, delay, error)
                    logger.warning(
                        "Evento %s falhou (tentativa %s); nova tentativa em %ss: %s",
                        event.id, event.attempts, int(delay.total_seconds()), error,
                    )
            return

        async with self._session_factory() as db:
            await queue.mark_done(db, event.id)
        logger.info(
            "Evento %s (%s) processado em %.0f ms.",
            event.id, event.kind, (time.monotonic() - started) * 1000,
        )

    async def maintenance(self, now: float | None = None) -> None:
        """Devolve eventos presos à fila e apaga os antigos já processados."""
        now = time.monotonic() if now is None else now
        if now - self._last_requeue >= REQUEUE_EVERY:
            self._last_requeue = now
            async with self._session_factory() as db:
                n = await queue.requeue_stale(db, STALE_AFTER)
            if n:
                logger.warning("%s evento(s) preso(s) em processing voltaram à fila.", n)
        if now - self._last_purge >= PURGE_EVERY:
            self._last_purge = now
            async with self._session_factory() as db:
                n = await queue.purge_done(db, KEEP_DONE_FOR)
            if n:
                logger.info("%s evento(s) antigo(s) removido(s) da fila.", n)
        if self._last_renew is None or now - self._last_renew >= RENEW_EVERY:
            self._last_renew = now
            try:
                async with self._session_factory() as db:
                    counts = await token_service.refresh_expiring(db)
                if any(counts.values()):
                    logger.info("Renovação de tokens: %s", counts)
            except Exception:  # noqa: BLE001
                logger.exception("Falha na renovação proativa dos tokens.")


# Instância do processo (usada pelo lifespan e pelo endpoint do webhook).
worker = WebhookWorker()


def notify() -> None:
    worker.notify()


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(_main())
