"""Engine com estado (F.3): resposta rápida, pergunta, timeout, atraso e janela de 24h.

Postgres de verdade + Meta falsa. Cobre iniciar, retomar por resposta e retomar pelo worker.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from app import crud
from app.models.account import InstagramAccount
from app.models.automation import Automation, TriggerType
from app.models.contact import Contact
from app.models.flow_run import FlowRun
from app.models.message import Message
from app.models.message_log import MessageLog
from app.services import automation_engine as engine
from app.services import instagram_api, token_service
from app.services.send_limiter import SendDeferred
from app.workers.webhook_worker import WebhookWorker
from tests.conftest import requires_pg

pytestmark = requires_pg


class FakeMeta:
    def __init__(self):
        self.calls: list[tuple] = []
        self.fail_quick_in_private = False
        self.fail_all_code: int | None = None

    def _maybe_fail(self):
        if self.fail_all_code is not None:
            raise instagram_api.InstagramAPIError(f"HTTP 400: erro (code {self.fail_all_code})", 400, self.fail_all_code)

    async def private(self, ig_user_id, comment_id, text, access_token, buttons=None):
        self._maybe_fail()
        self.calls.append(("private", comment_id, text))

    async def send(self, ig_user_id, recipient_id, text, access_token, buttons=None):
        self._maybe_fail()
        self.calls.append(("send", recipient_id, text))

    async def quick(self, ig_user_id, recipient, text, replies, access_token):
        self._maybe_fail()
        if self.fail_quick_in_private and "comment_id" in recipient:
            raise instagram_api.InstagramAPIError("HTTP 400: quick_replies não suportado", 400, 100)
        self.calls.append(("quick", recipient, text, [r["title"] for r in replies],
                           [r["payload"] for r in replies]))

    async def image(self, ig_user_id, recipient_id, url, access_token):
        self._maybe_fail()
        self.calls.append(("image", recipient_id, url))

    async def public(self, comment_id, message, access_token):
        self.calls.append(("public", comment_id, message))

    async def profile(self, igsid, token):
        return {}

    def sent(self):
        return [c for c in self.calls if c[0] in ("private", "send", "quick", "image")]


@pytest.fixture
def meta(monkeypatch):
    fake = FakeMeta()
    monkeypatch.setattr(instagram_api, "reply_privately_to_comment", fake.private)
    monkeypatch.setattr(instagram_api, "send_message_to_user", fake.send)
    monkeypatch.setattr(instagram_api, "send_quick_replies", fake.quick)
    monkeypatch.setattr(instagram_api, "send_image", fake.image)
    monkeypatch.setattr(instagram_api, "reply_publicly_to_comment", fake.public)
    monkeypatch.setattr(instagram_api, "get_user_profile", fake.profile)

    async def token(db, account):
        return "TOKEN"

    monkeypatch.setattr(token_service, "get_valid_token", token)
    monkeypatch.setattr(token_service, "read_token", lambda account: "TOKEN")
    return fake


@pytest.fixture
async def db(pg_sessions):
    async with pg_sessions() as session:
        session.add(InstagramAccount(ig_user_id="acc", ig_id="igid", access_token_enc="x"))
        await session.commit()
        yield session


def msg(i, t, **kw):
    return {"id": i, "type": "message", "text": t, **kw}


def qr(i="n1", t="Quer o link?", **kw):
    return msg(i, t, quick_replies=[{"id": "q1", "title": "Quero"}, {"id": "q2", "title": "Agora não"}], **kw)


def edge(s, t, b=None):
    return {"source": s, "target": t, **({"branch": b} if b else {})}


def g3(nodes, edges, start=None):
    return {"version": 3, "start": start or nodes[0]["id"], "nodes": nodes, "edges": edges}


async def add_auto(db, graph, trigger=TriggerType.COMMENT_ANY, **kw):
    auto = Automation(account_id="acc", name="auto", trigger=trigger, graph=graph, **kw)
    db.add(auto)
    await db.commit()
    return auto


async def runs(db):
    await db.commit()
    db.expire_all()
    return list((await db.execute(select(FlowRun).order_by(FlowRun.id))).scalars())


async def the_run(db):
    [run] = await runs(db)
    return run


async def comment(db, comment_id="c1", t="quero", **kw):
    await engine.process_comment(db, "igid", comment_id, t, "p1", "u1", "fulano", **kw)


async def dm(db, t, mid, payload=None, sender="u1", **kw):
    await engine.process_inbound_message(db, "igid", sender, t, mid=mid, quick_reply_payload=payload, **kw)


async def make_due(db, run_id):
    await db.execute(text("update flow_runs set resume_at = now() - interval '1 minute' where id=:i"), {"i": run_id})
    await db.commit()


async def contact(db, igsid="u1"):
    return (await db.execute(select(Contact).where(Contact.ig_user_id == igsid))).scalars().one()


async def out_texts(db):
    rows = await db.execute(select(Message.text).where(Message.direction == "out").order_by(Message.id))
    return list(rows.scalars())


# ═══ Comentário → private reply com respostas rápidas → toque → próximo nó ═══


def fluxo_comentario():
    return g3(
        [qr(), msg("sim", "Valeu {{username}}!"), msg("nao", "Tudo bem")],
        [edge("n1", "sim", "qr:q1"), edge("n1", "nao", "qr:q2")],
    )


async def test_comentario_resposta_rapida_continua_o_flow(db, meta):
    await add_auto(db, fluxo_comentario())
    # outra automação que casaria com o texto "Quero": a captura da resposta vem ANTES
    await add_auto(db, g3([msg("k", "NÃO DEVIA SAIR")], []), trigger=TriggerType.DM_KEYWORD, keyword="quero")

    await comment(db)
    assert meta.calls == [("quick", {"comment_id": "c1"}, "Quer o link?", ["Quero", "Agora não"],
                           ["qr:n1:q1", "qr:n1:q2"])]
    run = await the_run(db)
    assert run.status == "waiting" and run.waiting_for == "reply" and run.current_node_id == "n1"
    assert run.resume_at > datetime.now(timezone.utc) + timedelta(hours=22)   # prazo de 23 h
    assert run.trigger_ref == "c1" and run.graph["start"] == "n1"

    await dm(db, "Quero", "m1", payload="qr:n1:q1")
    assert meta.sent()[-1] == ("send", "u1", "Valeu fulano!")
    assert "NÃO DEVIA SAIR" not in str(meta.calls)
    run = await the_run(db)
    assert run.status == "completed" and run.finished_at is not None
    assert run.current_node_id == "sim"          # o log mostra o último nó executado
    assert await out_texts(db) == ["Quer o link?\n\n[Quero] [Agora não]", "Valeu fulano!"]


async def test_toque_em_outra_opcao_segue_a_saida_dela(db, meta):
    await add_auto(db, fluxo_comentario())
    await comment(db)
    await dm(db, "Agora não", "m1", payload="qr:n1:q2")
    assert meta.sent()[-1] == ("send", "u1", "Tudo bem")


async def test_texto_livre_sem_saida_other_encerra_o_flow(db, meta):
    await add_auto(db, fluxo_comentario())
    await comment(db)
    n = len(meta.calls)
    await dm(db, "oi, tudo bem?", "m1")        # não tem aresta "other": fim do caminho
    assert len(meta.calls) == n
    assert (await the_run(db)).status == "completed"


async def test_idempotencia_reentrega_do_mesmo_evento_nao_duplica(db, meta):
    await add_auto(db, fluxo_comentario())
    await comment(db)
    await dm(db, "Quero", "m1", payload="qr:n1:q1")
    n = len(meta.calls)
    await dm(db, "Quero", "m1", payload="qr:n1:q1")   # a Meta reenviou o mesmo mid
    assert len(meta.calls) == n
    await comment(db)                                   # o mesmo comentário também
    assert len(meta.calls) == n


async def test_uma_execucao_ativa_por_contato_e_automacao(db, meta):
    await add_auto(db, fluxo_comentario())
    await comment(db, "c1")
    await comment(db, "c2")                    # outro comentário, mesmo contato, flow ainda esperando
    assert len(meta.sent()) == 1 and len(await runs(db)) == 1
    logs = (await db.execute(select(MessageLog.status).order_by(MessageLog.id))).scalars().all()
    assert list(logs) == ["sent", "skipped"]


# ═══ Pergunta ═══


async def test_pergunta_salva_a_resposta_e_usa_na_mensagem_seguinte(db, meta):
    graph = g3(
        [{"id": "p", "type": "question", "text": "Qual seu e-mail?", "save_as": "email"},
         {"id": "c", "type": "condition", "mode": "var_contains", "var": "email", "value": "@"},
         msg("ok", "Anotei {{email}}, {{username}}"), msg("ruim", "Isso não parece um e-mail")],
        [edge("p", "c", "answered"), edge("c", "ok", "yes"), edge("c", "ruim", "no")],
    )
    await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    assert meta.sent() == [("send", "u1", "Qual seu e-mail?")]
    run = await the_run(db)
    assert run.status == "waiting" and run.current_node_id == "p"

    await dm(db, "ana@x.com", "m2")
    run = await the_run(db)
    assert run.status == "completed" and run.context["vars"] == {"email": "ana@x.com"}
    assert meta.sent()[-1][2].startswith("Anotei ana@x.com")


async def test_pergunta_com_resposta_invalida_segue_o_outro_ramo(db, meta):
    graph = g3(
        [{"id": "p", "type": "question", "text": "E-mail?", "save_as": "email"},
         {"id": "c", "type": "condition", "mode": "var_contains", "var": "email", "value": "@"},
         msg("ok", "OK"), msg("ruim", "Isso não parece um e-mail")],
        [edge("p", "c", "answered"), edge("c", "ok", "yes"), edge("c", "ruim", "no")],
    )
    await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    await dm(db, "sem arroba", "m2")
    assert meta.sent()[-1] == ("send", "u1", "Isso não parece um e-mail")


async def test_execucao_esperando_captura_a_dm_em_vez_do_gatilho_de_palavra_chave(db, meta):
    graph = g3([{"id": "p", "type": "question", "text": "Qual seu nome?", "save_as": "nome"},
                msg("a", "Oi {{nome}}")], [edge("p", "a", "answered")])
    await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await add_auto(db, g3([msg("k", "Preço: R$ 10")], []), trigger=TriggerType.DM_KEYWORD, keyword="preço")
    await dm(db, "oi", "m1")                     # dm_any e dm_keyword ("preço" não aparece): só a pergunta
    await dm(db, "preço", "m2")                  # a resposta contém a palavra-chave, mas é capturada
    assert [c[2] for c in meta.sent()] == ["Qual seu nome?", "Oi preço"]


# ═══ Timeout e atraso (worker) ═══


async def test_timeout_pelo_worker_segue_a_saida_timeout(db, meta, pg_sessions):
    graph = g3([qr(timeout_hours=2), msg("t", "Ainda aí?")], [edge("n1", "t", "timeout")])
    await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    run = await the_run(db)
    assert run.status == "waiting" and run.resume_at < datetime.now(timezone.utc) + timedelta(hours=2, minutes=1)

    w = WebhookWorker(session_factory=pg_sessions)
    assert await w.run_flows() == 0                      # ainda não venceu
    await make_due(db, run.id)
    assert await w.run_flows() == 1
    assert meta.sent()[-1] == ("send", "u1", "Ainda aí?")
    assert (await the_run(db)).status == "completed"
    assert await w.run_flows() == 0                      # não repete


async def test_atraso_retoma_no_no_seguinte(db, meta, pg_sessions):
    graph = g3([msg("a", "Primeiro"), {"id": "d", "type": "delay", "hours": 0.1}, msg("b", "Segundo")],
               [edge("a", "d"), edge("d", "b")])
    await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    assert [c[2] for c in meta.sent()] == ["Primeiro"]
    run = await the_run(db)
    assert run.status == "waiting" and run.waiting_for == "timer" and run.current_node_id == "b"
    assert run.resume_at < datetime.now(timezone.utc) + timedelta(minutes=7)   # 0,1 h = 6 min
    await make_due(db, run.id)
    await WebhookWorker(session_factory=pg_sessions).run_flows()
    assert [c[2] for c in meta.sent()] == ["Primeiro", "Segundo"]
    assert (await the_run(db)).status == "completed"


# ═══ Servidor que dormiu (plano grátis do Render) ═══


async def sleep_through(db, contact_igsid, hours):
    """Como se o servidor tivesse dormido: a última DM e o prazo ficam no passado."""
    c = await contact(db, contact_igsid)
    c.last_inbound_at = datetime.now(timezone.utc) - timedelta(hours=hours)
    await db.execute(
        text("update flow_runs set resume_at = now() - make_interval(hours => :h) where contact_id=:c"),
        {"h": hours - 1, "c": c.id},
    )
    await db.commit()


async def test_ao_acordar_retoma_o_que_venceu_e_expira_o_que_passou_da_janela(db, meta, pg_sessions):
    delayed = g3([msg("a", "Primeiro"), {"id": "d", "type": "delay", "hours": 1}, msg("b", "Segundo")],
                 [edge("a", "d"), edge("d", "b")])
    await add_auto(db, delayed, trigger=TriggerType.DM_ANY)
    for sender in ("cedo", "tarde"):
        await dm(db, "oi", f"m-{sender}", sender=sender)
    await sleep_through(db, "cedo", 10)    # venceu há 9 h, janela ainda aberta
    await sleep_through(db, "tarde", 30)   # venceu há 29 h, janela fechada
    meta.calls.clear()

    worker = WebhookWorker(session_factory=pg_sessions)
    assert await worker.run_flows() == 2
    assert meta.sent() == [("send", "cedo", "Segundo")]
    by_status = {r.status: r for r in await runs(db)}
    assert set(by_status) == {"completed", "expired"}
    assert by_status["expired"].last_error == "outside_window"
    assert await worker.run_flows() == 0


async def test_timeout_vencido_durante_o_sono_expira_sem_enviar(db, meta, pg_sessions):
    graph = g3([qr(timeout_hours=2), msg("t", "Ainda aí?")], [edge("n1", "t", "timeout")])
    await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    await sleep_through(db, "u1", 26)
    meta.calls.clear()
    await WebhookWorker(session_factory=pg_sessions).run_flows()
    assert meta.sent() == []
    run = await the_run(db)
    assert run.status == "expired" and run.last_error == "outside_window"


async def test_uma_falha_na_retomada_nao_derruba_o_resto_do_lote(db, meta, pg_sessions, monkeypatch):
    """Depois de dormir vêm várias vencidas juntas: o erro de uma não pode travar as outras."""
    delayed = g3([msg("a", "Primeiro"), {"id": "d", "type": "delay", "hours": 1}, msg("b", "Segundo")],
                 [edge("a", "d"), edge("d", "b")])
    await add_auto(db, delayed, trigger=TriggerType.DM_ANY)
    for sender in ("quebra", "segue"):
        await dm(db, "oi", f"m-{sender}", sender=sender)
    first, second = await runs(db)
    for offset, run in ((2, first), (1, second)):   # a que quebra é reservada primeiro
        await db.execute(text("update flow_runs set resume_at = now() - make_interval(mins => :m) where id=:i"),
                         {"m": offset, "i": run.id})
    await db.commit()
    meta.calls.clear()

    calls = []

    async def token(_db, account):
        calls.append(account.ig_user_id)
        if len(calls) == 1:
            raise RuntimeError("falha inesperada")
        return "TOKEN"

    monkeypatch.setattr(token_service, "get_valid_token", token)
    assert await WebhookWorker(session_factory=pg_sessions).run_flows() == 2
    assert meta.sent() == [("send", "segue", "Segundo")]
    assert [r.status for r in await runs(db)] == ["failed", "completed"]


async def test_imagem_e_enviada_pela_send_api(db, meta):
    graph = g3([msg("a", "Olha isso"), {"id": "i", "type": "image", "url": "https://x.com/a.png"}],
               [edge("a", "i")])
    await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    assert meta.sent() == [("send", "u1", "Olha isso"), ("image", "u1", "https://x.com/a.png")]
    assert await out_texts(db) == ["Olha isso", "[imagem] https://x.com/a.png"]


# ═══ Janela de 24h ═══


async def test_comentario_sem_janela_so_a_private_reply_e_o_resto_expira(db, meta):
    graph = g3([msg("a", "Primeiro"), msg("b", "Segundo")], [edge("a", "b")])
    await add_auto(db, graph)
    await comment(db)
    assert [c[0] for c in meta.sent()] == ["private"]
    run = await the_run(db)
    assert run.status == "expired" and run.last_error == "outside_window"
    assert run.current_node_id == "b"            # parou no nó que não pôde ser enviado


async def test_atraso_que_vence_com_a_janela_fechada_expira_sem_enviar(db, meta, pg_sessions):
    graph = g3([msg("a", "Primeiro"), {"id": "d", "type": "delay", "hours": 1}, msg("b", "Segundo")],
               [edge("a", "d"), edge("d", "b")])
    await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    run = await the_run(db)
    c = await contact(db)
    c.last_inbound_at = datetime.now(timezone.utc) - timedelta(hours=30)   # a janela fechou no meio
    await db.commit()
    await make_due(db, run.id)
    await WebhookWorker(session_factory=pg_sessions).run_flows()
    assert [x[2] for x in meta.sent()] == ["Primeiro"]
    run = await the_run(db)
    assert run.status == "expired" and run.last_error == "outside_window"


async def test_toque_na_resposta_rapida_abre_a_janela_do_comentario(db, meta):
    """Comentário (sem janela) → private reply com respostas → o toque abre a janela → segue."""
    await add_auto(db, fluxo_comentario())
    await comment(db)
    assert (await contact(db)).last_inbound_at is None
    await dm(db, "Quero", "m1", payload="qr:n1:q1")
    assert (await contact(db)).last_inbound_at is not None
    assert meta.sent()[-1][0] == "send"


# ═══ Falhas e bordas ═══


async def test_private_reply_recusa_respostas_rapidas_cai_para_texto(db, meta):
    meta.fail_quick_in_private = True
    await add_auto(db, fluxo_comentario())
    await comment(db)
    assert meta.calls == [("private", "c1", "Quer o link?")]
    run = await the_run(db)
    assert run.status == "waiting" and run.last_error == "quick_replies_unsupported_in_private_reply"
    # o contato responde em texto livre e o flow continua (sem saída "other": fim)
    await dm(db, "quero sim", "m1")
    assert (await the_run(db)).status == "completed"


async def test_erro_190_no_envio_marca_a_conta_e_falha_a_execucao(db, meta):
    meta.fail_all_code = 190
    await add_auto(db, fluxo_comentario())
    await comment(db)
    run = await the_run(db)
    assert run.status == "failed" and "190" in (run.last_error or "")
    acc = await db.get(InstagramAccount, "acc")
    await db.refresh(acc)
    assert acc.token_invalid_at is not None
    [log] = (await db.execute(select(MessageLog))).scalars().all()
    assert log.status == "failed"


async def test_mencao_em_story_nao_conta_como_resposta(db, meta):
    await add_auto(db, fluxo_comentario())
    await comment(db)                                         # run esperando resposta
    await add_auto(db, g3([msg("s", "Obrigado pela menção")], []), trigger=TriggerType.STORY_MENTION)
    await engine.process_inbound_message(
        db, "igid", "u1", "", mid="m9", attachments=[{"type": "story_mention"}])
    assert meta.sent()[-1] == ("send", "u1", "Obrigado pela menção")
    runs_ = await runs(db)
    assert [r.status for r in runs_] == ["waiting", "completed"]      # a primeira segue esperando


async def test_quick_reply_de_outra_mensagem_vira_other(db, meta):
    graph = g3([qr(), msg("o", "Não entendi")], [edge("n1", "o", "other")])
    await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    await dm(db, "Quero", "m2", payload="qr:outro_no:q1")
    assert meta.sent()[-1] == ("send", "u1", "Não entendi")


async def test_automacao_desativada_cancela_a_execucao_no_timeout(db, meta, pg_sessions):
    graph = g3([qr(), msg("t", "Ainda aí?")], [edge("n1", "t", "timeout")])
    auto = await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    auto.enabled = False
    await db.commit()
    run = await the_run(db)
    await make_due(db, run.id)
    await WebhookWorker(session_factory=pg_sessions).run_flows()
    assert len(meta.sent()) == 1
    assert (await the_run(db)).status == "cancelled"


async def test_editar_a_automacao_nao_quebra_quem_esta_no_meio(db, meta):
    auto = await add_auto(db, fluxo_comentario())
    await comment(db)
    auto.graph = g3([msg("x", "FLOW NOVO")], [])      # o dono edita enquanto o contato espera
    await db.commit()
    await dm(db, "Quero", "m1", payload="qr:n1:q1")
    assert meta.sent()[-1] == ("send", "u1", "Valeu fulano!")   # segue o grafo copiado na execução


class Deferring:
    """Limitador que manda esperar; `n` = quantas reservas ainda deixa passar."""

    def __init__(self, delay=120.0, allow=0):
        self.delay, self.allow = delay, allow

    async def reserve(self, account_id, sends=1, private_replies=0):
        if self.allow > 0:
            self.allow -= 1
            return None
        return self.delay


async def test_limitador_adia_o_inicio_sem_criar_execucao_nem_enviar(db, meta):
    await add_auto(db, fluxo_comentario())
    with pytest.raises(SendDeferred):
        await comment(db, limiter=Deferring())
    assert meta.calls == [] and await runs(db) == []


async def test_limitador_adia_a_retomada_do_worker_e_a_execucao_volta_a_esperar(db, meta):
    graph = g3([qr(), msg("t", "Ainda aí?")], [edge("n1", "t", "timeout")])
    await add_auto(db, graph, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    run = await the_run(db)
    await make_due(db, run.id)
    n = len(meta.calls)
    assert await engine.resume_due_runs(db, Deferring(delay=300)) == 1
    run = await the_run(db)
    assert len(meta.calls) == n and run.status == "waiting"
    assert run.resume_at > datetime.now(timezone.utc) + timedelta(minutes=4)


async def test_grafo_v2_antigo_funciona_de_ponta_a_ponta_e_termina_completed(db, meta):
    v2 = {"version": 2, "start": "m1",
          "nodes": [{"id": "m1", "type": "message", "text": "Oi!"},
                    {"id": "c1", "type": "condition", "mode": "is_new_contact"},
                    {"id": "m2", "type": "message", "text": "Bem-vindo"},
                    {"id": "m3", "type": "message", "text": "De volta"}],
          "edges": [edge("m1", "c1"), edge("c1", "m2", "yes"), edge("c1", "m3", "no")]}
    await add_auto(db, v2, trigger=TriggerType.DM_ANY)
    await dm(db, "oi", "m1")
    assert [c[2] for c in meta.sent()] == ["Oi!", "Bem-vindo"]
    run = await the_run(db)
    assert run.status == "completed" and run.graph["version"] == 2
