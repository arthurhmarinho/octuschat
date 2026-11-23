"""Testes puros: corpo do webhook → eventos da fila, e o despacho ao engine."""

import pytest

from app.services import webhook_events
from app.services.webhook_events import COMMENT, MESSAGE, extract_events


def comment_change(cid="c1", text="quero", media="p1", uid="u1", field="comments"):
    return {
        "field": field,
        "value": {
            "id": cid,
            "text": text,
            "media": {"id": media},
            "from": {"id": uid, "username": "fulano"},
        },
    }


def messaging(mid="m1", text="oi", sender="u2", **extra):
    msg = {"mid": mid, "text": text, **extra}
    return {"sender": {"id": sender}, "recipient": {"id": "acc"}, "message": msg}


def test_corpo_vazio_ou_sem_entry():
    assert extract_events({}) == []
    assert extract_events({"entry": []}) == []
    assert extract_events({"entry": None}) == []


def test_comentario_vira_evento_com_dedupe_pelo_id():
    body = {"entry": [{"id": "acc", "changes": [comment_change()]}]}
    [ev] = extract_events(body)
    assert ev["kind"] == COMMENT
    assert ev["account_id"] == "acc"
    assert ev["dedupe_key"] == "comment:c1"
    assert ev["payload"]["value"]["text"] == "quero"


def test_outros_campos_de_changes_sao_ignorados():
    body = {"entry": [{"id": "acc", "changes": [comment_change(field="mentions")]}]}
    assert extract_events(body) == []


def test_mensagem_vira_evento_com_dedupe_pelo_mid():
    body = {"entry": [{"id": "acc", "messaging": [messaging()]}]}
    [ev] = extract_events(body)
    assert ev["kind"] == MESSAGE
    assert ev["dedupe_key"] == "mid:m1"
    assert ev["payload"]["event"]["sender"]["id"] == "u2"


def test_eco_e_eventos_sem_message_sao_ignorados():
    body = {
        "entry": [
            {
                "id": "acc",
                "messaging": [
                    messaging(mid="eco", is_echo=True),
                    {"sender": {"id": "u"}, "read": {"mid": "x"}},
                    {"sender": {"id": "u"}, "message": {}},
                ],
            }
        ]
    }
    assert extract_events(body) == []


def test_lote_com_varias_entradas_preserva_ordem():
    body = {
        "entry": [
            {"id": "a1", "changes": [comment_change("c1"), comment_change("c2")]},
            {"id": "a2", "messaging": [messaging("m1"), messaging("m2")]},
        ]
    }
    keys = [e["dedupe_key"] for e in extract_events(body)]
    assert keys == ["comment:c1", "comment:c2", "mid:m1", "mid:m2"]


def test_sem_id_usa_hash_estavel_e_distinto():
    sem_id = {"field": "comments", "value": {"text": "x"}}
    body = {"entry": [{"id": "acc", "changes": [sem_id]}]}
    k1 = extract_events(body)[0]["dedupe_key"]
    k2 = extract_events(body)[0]["dedupe_key"]
    assert k1 == k2 and k1.startswith("comment:sha256:")
    outro = {"entry": [{"id": "acc", "changes": [{"field": "comments", "value": {"text": "y"}}]}]}
    assert extract_events(outro)[0]["dedupe_key"] != k1


def test_mencao_em_story_preserva_attachments():
    att = [{"type": "story_mention", "payload": {"url": "https://x"}}]
    body = {"entry": [{"id": "acc", "messaging": [messaging(text=None, attachments=att)]}]}
    [ev] = extract_events(body)
    assert ev["payload"]["event"]["message"]["attachments"] == att


# ── dispatch: dados do evento + limitador do worker ──


@pytest.fixture
def capturado(monkeypatch):
    calls = {}

    async def fake_comment(**kw):
        calls["comment"] = kw

    async def fake_inbound(**kw):
        calls["inbound"] = kw

    monkeypatch.setattr(webhook_events, "process_comment", fake_comment)
    monkeypatch.setattr(webhook_events, "process_inbound_message", fake_inbound)
    return calls


async def test_dispatch_comentario(capturado):
    [ev] = extract_events({"entry": [{"id": "acc", "changes": [comment_change()]}]})
    await webhook_events.dispatch("DB", ev["kind"], ev["account_id"], ev["payload"])
    assert capturado["comment"] == {
        "db": "DB",
        "account_id": "acc",
        "comment_id": "c1",
        "text": "quero",
        "post_id": "p1",
        "from_user": "u1",
        "from_username": "fulano",
        "limiter": None,
    }


async def test_dispatch_mensagem(capturado):
    reply_to = {"story": {"id": "s1"}}
    [ev] = extract_events(
        {"entry": [{"id": "acc", "messaging": [messaging(reply_to=reply_to)]}]}
    )
    await webhook_events.dispatch("DB", ev["kind"], ev["account_id"], ev["payload"])
    assert capturado["inbound"] == {
        "db": "DB",
        "account_id": "acc",
        "sender_id": "u2",
        "text": "oi",
        "mid": "m1",
        "reply_to": reply_to,
        "attachments": None,
        "limiter": None,
        "quick_reply_payload": None,
    }


async def test_dispatch_tipo_desconhecido_nao_quebra(capturado):
    await webhook_events.dispatch("DB", "outro", "acc", {})
    assert capturado == {}


async def test_dispatch_repassa_o_payload_da_resposta_rapida(capturado):
    item = messaging()
    item["message"]["quick_reply"] = {"payload": "qr:n1:q1"}
    [ev] = extract_events({"entry": [{"id": "acc", "messaging": [item]}]})
    await webhook_events.dispatch("DB", ev["kind"], ev["account_id"], ev["payload"])
    assert capturado["inbound"]["quick_reply_payload"] == "qr:n1:q1"
