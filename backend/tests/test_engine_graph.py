"""Engine executando o grafo por um caminho único (Postgres + API da Meta falsa)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.account import InstagramAccount
from app.models.automation import Automation, TriggerType
from app.models.contact import Contact
from app.models.message import Message
from app.models.message_log import MessageLog
from app.services import automation_engine as engine
from app.services import instagram_api, token_service
from app.services.send_limiter import SendDeferred
from tests.conftest import requires_pg

pytestmark = requires_pg

BTN = [{"id": "b1", "type": "web_url", "label": "Site", "url": "https://x.com"}]


def graph(*nodes, edges=None):
    nodes = list(nodes)
    if edges is None:  # cadeia linear
        edges = [{"source": nodes[i - 1]["id"], "target": nodes[i]["id"]}
                 for i in range(1, len(nodes))]
    return {"version": 2, "start": nodes[0]["id"], "nodes": nodes, "edges": edges}


def msg(node_id, text, buttons=None):
    n = {"id": node_id, "type": "message", "text": text}
    if buttons:
        n["buttons"] = buttons
    return n


class FakeMeta:
    def __init__(self):
        self.calls = []
        self.fail_template = False
        self.fail_all = False

    async def private(self, ig_user_id, comment_id, text, access_token, buttons=None):
        self.calls.append(("private", comment_id, text, buttons))
        if self.fail_all or (buttons and self.fail_template):
            raise instagram_api.InstagramAPIError("HTTP 400: template recusado", 400)

    async def send(self, ig_user_id, recipient_id, text, access_token, buttons=None):
        self.calls.append(("send", recipient_id, text, buttons))

    async def public(self, comment_id, message, access_token):
        self.calls.append(("public", comment_id, message))

    async def profile(self, igsid, token):
        return {}


@pytest.fixture
def meta(monkeypatch):
    fake = FakeMeta()
    monkeypatch.setattr(instagram_api, "reply_privately_to_comment", fake.private)
    monkeypatch.setattr(instagram_api, "send_message_to_user", fake.send)
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


async def add_auto(db, g, trigger=TriggerType.COMMENT_ANY, **kw):
    auto = Automation(account_id="acc", name="auto", trigger=trigger, graph=g, **kw)
    db.add(auto)
    await db.commit()
    return auto


async def add_contact(db, igsid="u1", inbound_ago=None):
    c = Contact(account_id="acc", ig_user_id=igsid)
    if inbound_ago is not None:
        c.last_inbound_at = datetime.now(timezone.utc) - inbound_ago
    db.add(c)
    await db.commit()
    return c


async def out_texts(db):
    rows = await db.execute(
        select(Message.text).where(Message.direction == "out").order_by(Message.id)
    )
    return list(rows.scalars())


async def logs(db):
    return list((await db.execute(select(MessageLog))).scalars())


async def comment(db, comment_id="c1", text="quero", **kw):
    await engine.process_comment(
        db, "igid", comment_id, text, "p1", "u1", "fulano", **kw
    )


# ── Comentário ──────────────────────────────────────────────


async def test_comentario_contato_novo_so_envia_a_private_reply(db, meta):
    await add_auto(db, graph(msg("m1", "Oi", BTN), msg("m2", "Segunda")), public_reply="Enviei!")
    await comment(db)
    assert meta.calls == [
        ("private", "c1", "Oi", BTN),
        ("public", "c1", "Enviei!"),
    ]  # m2 fica de fora: sem DM do contato, a janela de 24h está fechada
    assert await out_texts(db) == ["Oi\n\n[Site] → https://x.com"]
    [log] = await logs(db)
    assert log.status == "sent" and log.comment_id == "c1"


async def test_comentario_com_janela_aberta_segue_pela_send_api(db, meta):
    await add_contact(db, inbound_ago=timedelta(hours=2))
    await add_auto(db, graph(msg("m1", "Oi"), msg("m2", "Segunda")))
    await comment(db)
    assert meta.calls == [("private", "c1", "Oi", None), ("send", "u1", "Segunda", None)]
    assert await out_texts(db) == ["Oi", "Segunda"]


async def test_comentario_janela_vencida_nao_envia_o_resto(db, meta):
    await add_contact(db, inbound_ago=timedelta(hours=25))
    await add_auto(db, graph(msg("m1", "Oi"), msg("m2", "Segunda")))
    await comment(db)
    assert [c[0] for c in meta.calls] == ["private"]


async def test_fallback_do_button_template_vira_private_reply_com_links(db, meta):
    meta.fail_template = True
    await add_auto(db, graph(msg("m1", "Oi", BTN)))
    await comment(db)
    assert meta.calls == [
        ("private", "c1", "Oi", BTN),
        ("private", "c1", "Oi\n\n👉 Site: https://x.com", None),
    ]
    assert await out_texts(db) == ["Oi\n\n👉 Site: https://x.com"]
    [log] = await logs(db)
    assert log.status == "sent"


async def test_falha_ate_no_fallback_registra_failed_sem_segredo(db, meta):
    meta.fail_all = True
    await add_auto(db, graph(msg("m1", "Oi", BTN), msg("m2", "x")))
    await comment(db)
    [log] = await logs(db)
    assert log.status == "failed" and "template recusado" in log.error
    assert await out_texts(db) == []
    assert not [c for c in meta.calls if c[0] == "send"]


async def test_comentario_repetido_e_ignorado(db, meta):
    await add_auto(db, graph(msg("m1", "Oi")))
    await comment(db)
    await comment(db)
    assert len([c for c in meta.calls if c[0] == "private"]) == 1


async def test_comentario_nao_conta_como_dm_para_a_janela(db, meta):
    await add_auto(db, graph(msg("m1", "Oi")))
    await comment(db)
    contact = (await db.execute(select(Contact))).scalar_one()
    assert contact.last_message_at is not None
    assert contact.last_inbound_at is None


# ── DM / story ──────────────────────────────────────────────


COND_GRAPH = graph(
    msg("m1", "Olá"),
    {"id": "c", "type": "condition", "mode": "is_new_contact"},
    msg("novo", "Bem-vindo"),
    msg("velho", "De volta?"),
    edges=[
        {"source": "m1", "target": "c"},
        {"source": "c", "target": "novo", "branch": "yes"},
        {"source": "c", "target": "velho", "branch": "no"},
    ],
)


async def test_dm_executa_o_grafo_todo_pela_send_api(db, meta):
    await add_auto(db, COND_GRAPH, trigger=TriggerType.DM_KEYWORD, keyword="oi")
    await engine.process_inbound_message(db, "igid", "u1", "oi!", mid="mid1")
    assert meta.calls == [("send", "u1", "Olá", None), ("send", "u1", "Bem-vindo", None)]
    contact = (await db.execute(select(Contact))).scalar_one()
    assert contact.last_inbound_at is not None
    [log] = await logs(db)
    assert log.comment_id == "mid1" and log.status == "sent"


async def test_dm_contato_antigo_segue_o_ramo_nao(db, meta):
    await add_contact(db)
    await add_auto(db, COND_GRAPH, trigger=TriggerType.DM_ANY)
    await engine.process_inbound_message(db, "igid", "u1", "qualquer", mid="mid1")
    assert [c[2] for c in meta.calls] == ["Olá", "De volta?"]


async def test_story_mention_usa_o_mesmo_caminho(db, meta):
    await add_auto(db, graph(msg("m1", "Valeu pela menção!")), trigger=TriggerType.STORY_MENTION)
    await engine.process_inbound_message(
        db, "igid", "u1", "", mid="mid1", attachments=[{"type": "story_mention"}]
    )
    assert meta.calls == [("send", "u1", "Valeu pela menção!", None)]


# ── Limitador ───────────────────────────────────────────────


class Recorder:
    def __init__(self, delay=None):
        self.delay = delay
        self.calls = []

    async def reserve(self, account_id, sends=1, private_replies=0):
        self.calls.append((account_id, sends, private_replies))
        return self.delay


async def test_limitador_recebe_os_envios_previstos(db, meta):
    await add_auto(db, graph(msg("m1", "a"), msg("m2", "b"), msg("m3", "c")))
    lim = Recorder()
    await comment(db, limiter=lim)  # contato novo: só a private reply sai
    await add_contact(db, "u2", inbound_ago=timedelta(minutes=5))
    await engine.process_comment(db, "igid", "c2", "x", "p1", "u2", limiter=lim)
    assert lim.calls == [("acc", 1, 1), ("acc", 3, 1)]


async def test_limitador_adia_antes_de_qualquer_efeito(db, meta):
    await add_auto(db, graph(msg("m1", "a"), msg("m2", "b")), trigger=TriggerType.DM_ANY)
    lim = Recorder(delay=30.0)
    with pytest.raises(SendDeferred):
        await engine.process_inbound_message(db, "igid", "u1", "oi", mid="mid1", limiter=lim)
    assert lim.calls == [("acc", 2, 0)]
    assert meta.calls == []
    # Nada gravado: o evento será reprocessado do zero.
    assert (await db.execute(select(Message))).first() is None
    assert (await db.execute(select(Contact))).first() is None
