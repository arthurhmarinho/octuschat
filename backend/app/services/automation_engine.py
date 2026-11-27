"""Motor de automação: evento → automação que casa → execução do flow.

Todo gatilho (comentário, DM, story) vira uma EXECUÇÃO (`flow_runs`) do grafo
da automação, e o grafo é andado por `flow_runner.advance` (função pura):

1. um evento inicia a execução (`process_comment`, `process_inbound_message`);
2. a execução pode ESPERAR (toque numa resposta rápida, texto de uma Pergunta,
   atraso). Enquanto espera, o estado fica em `flow_runs`;
3. a resposta do contato a retoma (`process_inbound_message` captura a DM ANTES
   de qualquer gatilho de palavra-chave), e o worker retoma o que venceu
   (`resume_due_runs`: timeout de resposta e fim de atraso).

Envio: o 1º envio de um comentário é a private reply (não depende da janela
de 24h); todos os demais saem pela Send API e exigem a janela de 24h aberta
(`messenger`). Sem janela, a execução vira `expired` e nada é enviado.

Idempotência e falhas — decisão: **o estado é gravado ANTES de enviar as ações
do trecho** (at-most-once). Se o processo cair depois de gravar e antes de
enviar, aquele trecho se perde (nunca sai duplicado); a reentrega do evento não
reexecuta nada, porque o estado já avançou e a execução ativa é única por
(automação, contato). `message_logs` continua marcando o comentário/mid que
iniciou ou retomou a execução.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.security import redact_secrets
from app.models.account import InstagramAccount
from app.models.automation import Automation
from app.models.contact import Contact
from app.models.flow_run import FlowRun
from app.models.message_log import MessageLog
from app.services import flow_runner, instagram_api, messenger, token_service
from app.services.send_limiter import NoLimit, SendDeferred, SendLimiter

logger = logging.getLogger("inboxpilot.engine")

FALLBACK_QR_ERROR = "quick_replies_unsupported_in_private_reply"
OUTSIDE_WINDOW = "outside_window"


async def _enrich_contact(
    db: AsyncSession, account: InstagramAccount, contact: Contact, token: str
) -> None:
    """Preenche foto (e username, se faltar) do contato via API. Best-effort."""
    if contact.profile_pic and contact.username:
        return
    try:
        prof = await instagram_api.get_user_profile(contact.ig_user_id, token)
        await crud.contact.upsert(
            db,
            account.ig_user_id,
            contact.ig_user_id,
            username=prof.get("username") or contact.username,
            profile_pic=prof.get("profile_pic"),
            touch=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("Sem perfil enriquecido p/ %s: %s", contact.ig_user_id, exc)


def _store_body(text: str, buttons: list | None) -> str:
    """Texto como fica gravado na conversa (anexa botões de forma legível)."""
    stored = text
    if buttons:
        stored += "\n\n" + "\n".join(
            f"[{b['label']}] → {b['url']}" for b in buttons if b.get("url")
        )
    return stored


def _store_body_quick(text: str, replies: list[dict]) -> str:
    """Mensagem com respostas rápidas, como fica na conversa."""
    return f"{text}\n\n" + " ".join(f"[{r['title']}]" for r in replies)


@dataclass
class RunResult:
    first_sent: bool = False
    error: str | None = None
    sent: int = 0


# ── Planejamento (puro + limitador) ─────────────────────────


async def _reserve(
    limiter: SendLimiter,
    account_id: str,
    outcome: flow_runner.Outcome,
    *,
    private_reply: bool,
    window_open: bool,
) -> None:
    """Reserva no limitador os envios previstos ANTES de qualquer efeito.

    Levanta SendDeferred se o limitador mandar esperar.
    """
    n = len(outcome.actions)
    if not window_open:
        n = min(n, 1) if private_reply else 0  # sem janela, só a private reply sai
    if n:
        delay = await limiter.reserve(
            account_id, sends=n, private_replies=1 if private_reply else 0
        )
        if delay:
            raise SendDeferred(delay)


def _context(text: str, is_new: bool, username: str | None) -> dict:
    return {"text": text, "is_new_contact": is_new, "username": username or "", "vars": {}}


# ── Execução ────────────────────────────────────────────────


async def _persist_state(db: AsyncSession, run: FlowRun, outcome: flow_runner.Outcome) -> None:
    """Grava contexto e próximo estado ANTES de enviar as ações (ver docstring)."""
    state = outcome.next_state
    if state.get("status") == "waiting":
        resume_at = datetime.now(timezone.utc) + timedelta(hours=state["resume_in_hours"])
        await crud.flow_run.save(
            db,
            run,
            context=outcome.context,
            status="waiting",
            waiting_for=state["waiting_for"],
            current_node_id=state["node_id"],
            resume_at=resume_at,
        )
    else:
        # Segue andando (ou concluindo): deixa de esperar.
        await crud.flow_run.save(
            db,
            run,
            context=outcome.context,
            status="running",
            waiting_for=None,
            resume_at=None,
            # Onde a execução "parou" (log): o último nó que ela processou.
            current_node_id=outcome.last_node_id or run.current_node_id,
        )


async def _send_actions(
    db: AsyncSession,
    account: InstagramAccount,
    run: FlowRun,
    outcome: flow_runner.Outcome,
    token: str,
    *,
    contact: Contact,
    source: str,
    comment_id: str | None = None,
) -> RunResult:
    """Envia as ações em ordem e grava cada uma na conversa.

    Com `comment_id`, a 1ª ação é a private reply. As demais exigem a janela de
    24h: sem ela a execução vira `expired` (e nada mais sai). Falha de envio
    vira `failed`.
    """
    result = RunResult()
    for i, action in enumerate(outcome.actions):
        private = i == 0 and bool(comment_id)
        kind = action["type"]
        try:
            if kind == "send_text":
                text, buttons = action["text"], action["buttons"]
                body = _store_body(text, buttons)
                if private:
                    sent_text = await messenger.send_private_reply(
                        account.ig_user_id, comment_id, text, buttons, token
                    )
                    if sent_text != text:  # caiu no fallback (links embutidos)
                        body = sent_text
                else:
                    await messenger.send_dm(account.ig_user_id, contact, text, buttons, token)
            elif kind == "send_quick_replies":
                text, replies = action["text"], action["replies"]
                body = _store_body_quick(text, replies)
                if private:
                    with_replies = await messenger.send_private_reply_quick_replies(
                        account.ig_user_id, comment_id, text, replies, token
                    )
                    if not with_replies:
                        body = text
                        await crud.flow_run.save(db, run, last_error=FALLBACK_QR_ERROR)
                else:
                    await messenger.send_dm_quick_replies(
                        account.ig_user_id, contact, text, replies, token
                    )
            elif kind == "send_image":
                body = f"[imagem] {action['url']}"
                await messenger.send_dm_image(account.ig_user_id, contact, action["url"], token)
            else:  # tipo de ação desconhecido: ignora
                logger.warning("Ação desconhecida: %s", kind)
                continue
        except messenger.OutsideWindow as exc:
            logger.info("Flow da execução %s parou: %s", run.id, exc)
            await crud.flow_run.save(db, run, current_node_id=action["node_id"])
            await crud.flow_run.finish(db, run, "expired", OUTSIDE_WINDOW)
            return result
        except Exception as exc:  # noqa: BLE001
            await token_service.note_api_error(db, account, exc)
            error = redact_secrets(str(exc))
            if i == 0:
                result.error = error
                logger.exception("Falha ao enviar a 1ª ação da execução %s: %s", run.id, exc)
            else:
                logger.warning("Falha na ação %s da execução %s: %s", i + 1, run.id, exc)
            await crud.flow_run.save(db, run, current_node_id=action["node_id"])
            await crud.flow_run.finish(db, run, "failed", error[:2000])
            return result
        if i == 0:
            result.first_sent = True
        result.sent += 1
        await crud.message.create(db, account.ig_user_id, contact.id, "out", body, source)
    return result


async def _step(
    db: AsyncSession,
    account: InstagramAccount,
    run: FlowRun,
    outcome: flow_runner.Outcome,
    token: str,
    *,
    contact: Contact,
    source: str,
    comment_id: str | None = None,
) -> RunResult:
    """Aplica um `Outcome`: grava o estado, envia as ações e fecha se acabou."""
    await _persist_state(db, run, outcome)
    result = await _send_actions(
        db, account, run, outcome, token, contact=contact, source=source, comment_id=comment_id
    )
    # Só conclui se ninguém encerrou a execução no meio (expired/failed) e ela não espera.
    if run.status == "running" and outcome.next_state.get("status") == "completed":
        await crud.flow_run.finish(db, run, "completed")
    return result


async def _start_run(
    db: AsyncSession,
    account: InstagramAccount,
    auto: Automation,
    contact: Contact,
    outcome: flow_runner.Outcome,
    context: dict,
    token: str,
    *,
    source: str,
    trigger_ref: str | None,
    comment_id: str | None = None,
) -> tuple[FlowRun | None, RunResult]:
    """Cria a execução (uma ativa por automação e contato) e a conduz."""
    graph = flow_runner.normalize_graph(auto.graph)
    run = await crud.flow_run.create(
        db,
        automation_id=auto.id,
        account_id=account.ig_user_id,
        contact_id=contact.id,
        graph={"version": (auto.graph or {}).get("version", 2), **graph},
        context=context,
        trigger_ref=trigger_ref,
        current_node_id=graph["start"],
    )
    if run is None:
        logger.info(
            "Automação '%s' já tem execução ativa para %s; ignorando o gatilho.",
            auto.name, contact.ig_user_id,
        )
        return None, RunResult()
    result = await _step(
        db, account, run, outcome, token, contact=contact, source=source, comment_id=comment_id
    )
    return run, result


# ── Gatilhos ────────────────────────────────────────────────


async def process_comment(
    db: AsyncSession,
    account_id: str,
    comment_id: str,
    text: str,
    post_id: str | None,
    from_user: str | None,
    from_username: str | None = None,
    limiter: SendLimiter | None = None,
) -> None:
    """Processa um comentário recebido via webhook."""
    limiter = limiter or NoLimit()
    # Idempotência: se já respondemos este comentário, ignora.
    if await crud.message_log.exists_for_comment(db, comment_id):
        logger.info("Comentário %s já processado, ignorando.", comment_id)
        return

    # O webhook identifica a conta por ig_id (≠ ig_user_id); casa por qualquer um.
    account = await crud.account.get_by_any_id(db, account_id)
    if account is None:
        logger.warning("Conta %s não conectada; nada a fazer.", account_id)
        return
    token = await token_service.get_valid_token(db, account)
    # Canoniza para o ig_user_id (chave das automações/contatos, usada no front).
    account_id = account.ig_user_id

    # Vincula automações "próxima publicação" se este comentário é de um post novo.
    if post_id:
        await crud.automation.bind_next_posts(db, account_id, post_id)

    matches = await crud.automation.find_matching(db, account_id, text, post_id)
    if not matches:
        return
    if not from_user:
        logger.warning("Comentário %s sem autor; não dá para iniciar o flow.", comment_id)
        return

    # Dispara a primeira automação que casou (1 resposta privada por comentário).
    auto = matches[0]
    existing = await crud.contact.find(db, account_id, from_user)
    outcome = flow_runner.advance(
        auto.graph,
        flow_runner.normalize_graph(auto.graph)["start"],
        _context(text, existing is None, from_username or (existing.username if existing else None)),
    )
    if not outcome.actions:
        logger.warning("Automação '%s' sem mensagens para enviar.", auto.name)
        return
    await _reserve(
        limiter, account_id, outcome,
        private_reply=True,
        window_open=existing is not None and messenger.window_open(existing),
    )

    contact = await crud.contact.upsert(db, account_id, from_user, username=from_username)
    await _enrich_contact(db, account, contact, token)
    outcome.context["username"] = contact.username or from_username or ""

    run, result = await _start_run(
        db, account, auto, contact, outcome, outcome.context, token,
        source="comment_reply", trigger_ref=comment_id, comment_id=comment_id,
    )
    if run is None:
        db.add(MessageLog(automation_id=auto.id, comment_id=comment_id,
                          recipient_id=from_user, status="skipped", error=None))
        await db.commit()
        return
    if result.first_sent:
        logger.info("Automação '%s' disparada para %s.", auto.name, from_user)

    # Resposta PÚBLICA opcional no comentário (best-effort, não bloqueia a DM).
    if auto.public_reply:
        try:
            await instagram_api.reply_publicly_to_comment(
                comment_id, auto.public_reply, token
            )
            logger.info("Resposta pública enviada no comentário %s.", comment_id)
        except Exception as exc:  # noqa: BLE001
            await token_service.note_api_error(db, account, exc)
            logger.warning("Falha na resposta pública: %s", exc)

    db.add(
        MessageLog(
            automation_id=auto.id,
            comment_id=comment_id,
            recipient_id=from_user,
            status="sent" if result.first_sent else "failed",
            error=result.error,
        )
    )
    await db.commit()


async def process_inbound_message(
    db: AsyncSession,
    account_id: str,
    sender_id: str,
    text: str,
    mid: str | None = None,
    reply_to: dict | None = None,
    attachments: list | None = None,
    limiter: SendLimiter | None = None,
    quick_reply_payload: str | None = None,
) -> None:
    """Registra a mensagem recebida e, se for o caso, responde.

    Ordem de prioridade:
    1. uma execução ESPERANDO resposta deste contato captura a mensagem (não
       dispara gatilho de palavra-chave para ela);
    2. senão, distingue o tipo pelo payload e procura um gatilho:
       - anexo ``story_mention`` → menção em story (sem texto/keyword);
       - ``reply_to.story`` → resposta a um story (keyword opcional);
       - caso contrário → DM comum.
    """
    limiter = limiter or NoLimit()
    if not sender_id:
        return
    attachments = attachments or []
    is_story_mention = any(
        (a or {}).get("type") == "story_mention" for a in attachments
    )
    # Menção em story costuma vir sem texto; demais fluxos exigem texto.
    if not text and not is_story_mention:
        return

    account = await crud.account.get_by_any_id(db, account_id)
    if account is None:
        return
    account_id = account.ig_user_id  # canoniza
    # Ignora eco das mensagens enviadas pela própria conta.
    if sender_id in (account_id, account.ig_id):
        return

    is_story_reply = bool((reply_to or {}).get("story")) and not is_story_mention
    if is_story_mention:
        source, kind = "story_mention", "Menção em story"
    elif is_story_reply:
        source, kind = "story_reply", "Resposta a story"
    else:
        source, kind = "dm", "Mensagem"
    # Menção sem texto: registra um marcador legível na conversa.
    inbound_text = text or "Mencionou você em um story"

    already = bool(mid) and await crud.message_log.exists_for_comment(db, mid)
    existing = await crud.contact.find(db, account_id, sender_id)

    # Decide (sem efeitos) o que vai acontecer — o limitador pode adiar o
    # evento, e aí ele é reprocessado do zero.
    waiting: FlowRun | None = None
    reply_outcome: flow_runner.Outcome | None = None
    auto, outcome = None, None
    if not already:
        if existing is not None and not is_story_mention:
            waiting = await crud.flow_run.find_waiting_reply(db, account_id, existing.id)
        if waiting is not None:
            reply_outcome = flow_runner.advance(
                waiting.graph, waiting.current_node_id, waiting.context,
                {"type": "reply", "text": text, "quick_reply_payload": quick_reply_payload},
            )
            # A mensagem que acabou de chegar abre a janela de 24h.
            await _reserve(limiter, account_id, reply_outcome, private_reply=False, window_open=True)
        else:
            if is_story_mention:
                matches = await crud.automation.find_matching_story_mention(db, account_id)
            elif is_story_reply:
                matches = await crud.automation.find_matching_story(db, account_id, text)
            else:
                matches = await crud.automation.find_matching_dm(db, account_id, text)
            if matches:
                auto = matches[0]
                outcome = flow_runner.advance(
                    auto.graph,
                    flow_runner.normalize_graph(auto.graph)["start"],
                    _context(text, existing is None, existing.username if existing else None),
                )
                await _reserve(limiter, account_id, outcome, private_reply=False, window_open=True)

    contact = await crud.contact.upsert(db, account_id, sender_id, inbound=True)
    await _enrich_contact(db, account, contact, token_service.read_token(account))
    await crud.message.create(db, account_id, contact.id, "in", inbound_text, source)
    logger.info("%s recebida de %s registrada.", kind, sender_id)

    # ── 1. Retomada por resposta ──
    if waiting is not None and reply_outcome is not None:
        token = await token_service.get_valid_token(db, account)
        # Pode ter mudado entre a decisão e agora (outro worker): só segue se ainda espera.
        await db.refresh(waiting)
        if waiting.status != "waiting" or waiting.waiting_for != "reply":
            return
        reply_outcome.context["username"] = contact.username or reply_outcome.context.get("username", "")
        result = await _step(
            db, account, waiting, reply_outcome, token, contact=contact, source=source
        )
        db.add(
            MessageLog(
                automation_id=waiting.automation_id,
                comment_id=mid or f"reply:{sender_id}:{waiting.id}",
                recipient_id=sender_id,
                status="sent" if result.error is None else "failed",
                error=result.error,
            )
        )
        await db.commit()
        return

    # ── 2. Gatilhos ──
    if auto is None or outcome is None or not outcome.actions:
        return
    token = await token_service.get_valid_token(db, account)
    outcome.context["username"] = contact.username or ""
    run, result = await _start_run(
        db, account, auto, contact, outcome, outcome.context, token,
        source=source, trigger_ref=mid,
    )
    if run is None:
        return
    if result.first_sent:
        logger.info("Automação de DM '%s' disparada para %s.", auto.name, sender_id)
    db.add(
        MessageLog(
            automation_id=auto.id,
            comment_id=mid or f"dm:{sender_id}:{contact.id}",
            recipient_id=sender_id,
            status="sent" if result.first_sent else "failed",
            error=result.error,
        )
    )
    await db.commit()


# ── Retomada pelo worker (timeouts e atrasos) ───────────────


async def resume_due_runs(
    db: AsyncSession, limiter: SendLimiter | None = None, limit: int = 20
) -> int:
    """Retoma as execuções cujo prazo venceu (chamado a cada ciclo do worker).

    - esperando RESPOSTA e o prazo acabou → segue a saída ``timeout``;
    - esperando um ATRASO e acabou → segue para o nó seguinte ao atraso.

    Devolve quantas execuções foram reservadas.
    """
    limiter = limiter or NoLimit()
    runs = await crud.flow_run.claim_due(db, limit)
    for run_id in [r.id for r in runs]:
        # Relê a cada volta: o rollback de uma falha expira tudo o que a sessão
        # carregou, inclusive as outras execuções já reservadas.
        run = await db.get(FlowRun, run_id, populate_existing=True)
        if run is None:  # a automação (ou o contato) foi apagada nesse meio-tempo
            continue
        try:
            await _resume_one(db, run, limiter)
        except SendDeferred as deferred:
            # Nada foi enviado: volta a esperar e tenta de novo quando o limitador deixar.
            await crud.flow_run.save(
                db, run, status="waiting",
                resume_at=datetime.now(timezone.utc) + timedelta(seconds=deferred.delay),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao retomar a execução %s: %s", run_id, exc)
            await db.rollback()
            run = await db.get(FlowRun, run_id, populate_existing=True)
            if run is not None:
                await crud.flow_run.finish(db, run, "failed", redact_secrets(str(exc))[:2000])
    return len(runs)


async def _resume_one(db: AsyncSession, run: FlowRun, limiter: SendLimiter) -> None:
    auto = await db.get(Automation, run.automation_id)
    if auto is None or not auto.enabled:
        await crud.flow_run.finish(db, run, "cancelled", "automation_disabled")
        return
    account = await crud.account.get(db, run.account_id)
    contact = await db.get(Contact, run.contact_id)
    if account is None or contact is None:
        await crud.flow_run.finish(db, run, "failed", "account_or_contact_missing")
        return

    event = {"type": "timeout"} if run.waiting_for == "reply" else None
    outcome = flow_runner.advance(run.graph, run.current_node_id, run.context, event)
    await _reserve(
        limiter, account.ig_user_id, outcome,
        private_reply=False, window_open=messenger.window_open(contact),
    )
    token = await token_service.get_valid_token(db, account)
    await _step(db, account, run, outcome, token, contact=contact, source="dm")
