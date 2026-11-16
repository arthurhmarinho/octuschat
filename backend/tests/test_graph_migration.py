"""Migração 0004: colunas antigas (mensagem 1 + flow) → grafo único.

- Conversão pura (`legacy_to_graph` / `graph_to_legacy`): sem banco.
- Upgrade/downgrade de verdade: precisa de TEST_DATABASE_URL (o schema do
  banco descartável é apagado!).
"""

import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.schemas.automation import FlowGraph
from app.services.flow_runner import plan_steps
from tests.conftest import TEST_DB, requires_pg

_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0004_unified_flow_graph.py"
_spec = importlib.util.spec_from_file_location("mig_0004", _PATH)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)

BTN = [{"label": "Site", "url": "https://exemplo.com"}]


def texts(graph, ctx=None):
    return [s["text"] for s in plan_steps(graph, ctx)]


# ── Formato 1: só a mensagem 1 (sem flow) ───────────────────


def test_sem_flow_vira_um_no():
    g = mig.legacy_to_graph("Oi!", BTN, None, None, None)
    assert g == {
        "version": 2,
        "start": "m1",
        "nodes": [{"id": "m1", "type": "message", "text": "Oi!",
                   "buttons": [{"id": "b1", "type": "web_url", **BTN[0]}]}],
        "edges": [],
    }
    FlowGraph.model_validate(g)


def test_link_sem_botoes_e_embutido_no_texto():
    g = mig.legacy_to_graph("Oi", None, "https://x.com", "Abrir", [])
    assert g["nodes"][0]["text"] == "Oi\n\n👉 Abrir: https://x.com"
    assert "buttons" not in g["nodes"][0]
    g = mig.legacy_to_graph("Oi", None, "https://x.com", None, None)
    assert g["nodes"][0]["text"] == "Oi\n\nhttps://x.com"


def test_link_com_botoes_e_ignorado_como_no_envio_antigo():
    g = mig.legacy_to_graph("Oi", BTN, "https://x.com", "Abrir", None)
    assert g["nodes"][0]["text"] == "Oi"


# ── Formato 2: flow em lista legada ─────────────────────────


def test_lista_legada_vira_cadeia_apos_a_mensagem_1():
    flow = [{"text": "dois"}, {"text": "três", "buttons": BTN}]
    g = mig.legacy_to_graph("um", None, None, None, flow)
    assert [n["id"] for n in g["nodes"]] == ["m1", "s0", "s1"]
    assert g["edges"] == [{"source": "m1", "target": "s0"},
                          {"source": "s0", "target": "s1"}]
    assert g["nodes"][2]["buttons"][0]["id"] == "b1"
    assert texts(g) == ["um", "dois", "três"]
    FlowGraph.model_validate(g)


def test_lista_legada_preserva_passos_vazios():
    g = mig.legacy_to_graph("um", None, None, None, [{"text": ""}, None, {"text": "fim"}])
    assert len(g["nodes"]) == 4  # nada é descartado
    assert texts(g) == ["um", "fim"]  # o engine pula os vazios, como antes


# ── Formato 3: flow em grafo ────────────────────────────────


GRAPH_FLOW = {
    "nodes": [
        {"id": "c", "type": "condition", "mode": "is_new_contact", "value": None},
        {"id": "a", "type": "message", "text": "novo", "buttons": BTN},
        {"id": "b", "type": "message", "text": "antigo", "buttons": None},
    ],
    "edges": [
        {"source": "c", "target": "a", "branch": "yes"},
        {"source": "c", "target": "b", "branch": "no"},
    ],
    "start": "c",
}


def test_grafo_antigo_e_pendurado_na_mensagem_1():
    g = mig.legacy_to_graph("oi", None, None, None, GRAPH_FLOW)
    assert g["start"] == "m1"
    assert g["edges"][0] == {"source": "m1", "target": "c"}
    assert {"source": "c", "target": "a", "branch": "yes"} in g["edges"]
    assert g["nodes"][1] == {"id": "c", "type": "condition", "mode": "is_new_contact"}
    assert texts(g, {"is_new_contact": True}) == ["oi", "novo"]
    assert texts(g, {"is_new_contact": False}) == ["oi", "antigo"]
    FlowGraph.model_validate(g)


def test_grafo_antigo_com_id_m1_nao_colide():
    flow = {"nodes": [{"id": "m1", "type": "message", "text": "x"}], "edges": [], "start": "m1"}
    g = mig.legacy_to_graph("oi", None, None, None, flow)
    assert g["start"] == "m1_"
    assert texts(g) == ["oi", "x"]


def test_grafo_antigo_sem_start_usa_o_primeiro_no():
    flow = {"nodes": [{"id": "z", "type": "message", "text": "x"}], "edges": []}
    g = mig.legacy_to_graph("oi", None, None, None, flow)
    assert texts(g) == ["oi", "x"]


# ── Ida e volta (downgrade) ─────────────────────────────────


@pytest.mark.parametrize(
    ("buttons", "flow"),
    [
        (BTN, None),
        (None, [{"text": "dois"}, {"text": "três", "buttons": BTN}]),
        (None, GRAPH_FLOW),
    ],
    ids=["sem-flow", "lista", "grafo"],
)
def test_ida_e_volta_preserva_os_dados(buttons, flow):
    g = mig.legacy_to_graph("um", buttons, None, None, flow)
    back = mig.graph_to_legacy(g)
    assert back["reply_message"] == "um"
    assert back["buttons"] == buttons
    if isinstance(flow, dict):
        assert back["flow"]["start"] == "c"
        assert {n["id"] for n in back["flow"]["nodes"]} == {"c", "a", "b"}
        assert sorted(map(json.dumps, back["flow"]["edges"])) == sorted(
            map(json.dumps, flow["edges"])
        )
    else:
        assert back["flow"] == flow


# ── Upgrade/downgrade contra o Postgres ─────────────────────


@pytest.fixture
def alembic_db(monkeypatch, fernet_key):
    from alembic import command
    from alembic.config import Config

    from app.core.config import settings

    monkeypatch.setattr(settings, "migrations_database_url", TEST_DB)
    engine = create_engine(TEST_DB)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
    )
    yield engine, (lambda rev: command.upgrade(cfg, rev)), (lambda rev: command.downgrade(cfg, rev))
    engine.dispose()


@requires_pg
def test_upgrade_e_downgrade_reais(alembic_db):
    engine, upgrade, downgrade = alembic_db
    upgrade("0003")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO instagram_accounts (ig_user_id, access_token_enc) VALUES ('acc', 'x')"
        ))
        rows = [
            (1, "só a 1", json.dumps(BTN), None, None, None),
            (2, "com link", None, "https://x.com", "Abrir", json.dumps([{"text": "dois"}])),
            (3, "com grafo", None, None, None, json.dumps(GRAPH_FLOW)),
        ]
        for r in rows:
            conn.execute(
                text(
                    "INSERT INTO automations (id, account_id, name, trigger, reply_message, "
                    "buttons, link_url, link_label, flow, bind_next, enabled) VALUES "
                    "(:id, 'acc', 'a', 'COMMENT_ANY', :rm, CAST(:b AS jsonb), :lu, :ll, "
                    "CAST(:f AS json), false, true)"
                ),
                dict(zip(["id", "rm", "b", "lu", "ll", "f"], r)),
            )
        conn.execute(text("INSERT INTO contacts (id, account_id, ig_user_id) VALUES (1, 'acc', 'u1'), (2, 'acc', 'u2')"))
        conn.execute(text(
            "INSERT INTO messages (account_id, contact_id, direction, text, source, created_at) VALUES "
            "('acc', 1, 'in', 'oi', 'dm', '2026-01-01T10:00:00Z'),"
            "('acc', 1, 'in', 'oi de novo', 'dm', '2026-01-02T10:00:00Z'),"
            "('acc', 2, 'out', 'resposta', 'comment_reply', '2026-01-03T10:00:00Z')"
        ))

    upgrade("0004")
    with engine.begin() as conn:
        graphs = dict(conn.execute(text("SELECT id, graph FROM automations ORDER BY id")).all())
        inbound = dict(conn.execute(text("SELECT id, last_inbound_at FROM contacts")).all())
    assert texts(graphs[1]) == ["só a 1"]
    assert graphs[1]["nodes"][0]["buttons"][0]["url"] == "https://exemplo.com"
    assert texts(graphs[2]) == ["com link\n\n👉 Abrir: https://x.com", "dois"]
    assert texts(graphs[3], {"is_new_contact": True}) == ["com grafo", "novo"]
    assert inbound[1].isoformat().startswith("2026-01-02")
    assert inbound[2] is None  # só recebeu (comentário), nunca mandou DM

    downgrade("0003")
    with engine.begin() as conn:
        back = {
            r.id: r for r in conn.execute(text(
                "SELECT id, reply_message, buttons, link_url, flow FROM automations ORDER BY id"
            ))
        }
    assert back[1].reply_message == "só a 1" and back[1].buttons == BTN and back[1].flow is None
    # O link foi embutido no texto: o engine antigo envia exatamente o mesmo.
    assert back[2].reply_message == "com link\n\n👉 Abrir: https://x.com"
    assert back[2].link_url is None and back[2].buttons is None
    assert back[2].flow == [{"text": "dois"}]
    assert back[3].flow["start"] == "c" and len(back[3].flow["nodes"]) == 3
