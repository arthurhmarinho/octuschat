"""Testes do flow_runner.plan_steps (função pura: grafo + contexto → mensagens)."""

import logging

import pytest

from app.services import flow_runner
from app.services.flow_runner import MAX_STEPS, normalize_graph, plan_steps

BTN = [{"label": "Abrir", "url": "https://exemplo.com"}]


def texts(steps: list[dict]) -> list[str]:
    return [s["text"] for s in steps]


def msg(node_id: str, text: str, buttons=None) -> dict:
    return {"id": node_id, "type": "message", "text": text, "buttons": buttons}


def cond(node_id: str, mode: str = "text_contains", value: str | None = None) -> dict:
    return {"id": node_id, "type": "condition", "mode": mode, "value": value}


def edge(source: str, target: str, branch: str | None = None) -> dict:
    e = {"source": source, "target": target}
    if branch:
        e["branch"] = branch
    return e


def chain(*steps) -> dict:
    """Grafo linear: cada item é um texto ou um nó de mensagem pronto."""
    nodes = [
        s if isinstance(s, dict) else msg(f"s{i}", s) for i, s in enumerate(steps)
    ]
    edges = [edge(nodes[i - 1]["id"], nodes[i]["id"]) for i in range(1, len(nodes))]
    return {"version": 2, "start": nodes[0]["id"] if nodes else None,
            "nodes": nodes, "edges": edges}


# ── Grafo vazio / incompleto ────────────────────────────────


@pytest.mark.parametrize("graph", [None, [], {}, {"nodes": [], "edges": []}])
def test_grafo_vazio_nao_envia_nada(graph):
    assert plan_steps(graph) == []


def test_normalize_graph_tolera_lixo():
    g = normalize_graph({"nodes": [None, msg("a", "x"), "lixo"], "edges": [1, edge("a", "b")]})
    assert g == {"nodes": [msg("a", "x")], "edges": [edge("a", "b")], "start": "a"}


# ── Cadeia linear ───────────────────────────────────────────


def test_cadeia_em_ordem_com_botoes_e_node_id():
    graph = chain("um", msg("d", "dois", BTN), "três")
    steps = plan_steps(graph)
    assert texts(steps) == ["um", "dois", "três"]
    assert [s["node_id"] for s in steps] == ["s0", "d", "s2"]
    assert steps[0]["buttons"] is None
    assert steps[1]["buttons"] == BTN


def test_cadeia_pula_mensagens_vazias_mas_segue():
    graph = chain("um", "   ", msg("b", "", BTN), "fim")
    steps = plan_steps(graph)
    # vazio é pulado; só-botões é enviado (texto vazio + botões)
    assert texts(steps) == ["um", "", "fim"]
    assert steps[1]["buttons"] == BTN


def test_texto_e_aparado():
    assert texts(plan_steps(chain("  oi  "))) == ["oi"]


# ── Grafo ───────────────────────────────────────────────────


def test_grafo_segue_arestas_e_nao_a_ordem_dos_nos():
    flow = {
        "nodes": [msg("c", "terceiro"), msg("a", "primeiro"), msg("b", "segundo")],
        "edges": [edge("a", "b"), edge("b", "c")],
        "start": "a",
    }
    assert texts(plan_steps(flow)) == ["primeiro", "segundo", "terceiro"]


def test_grafo_sem_start_comeca_no_primeiro_no():
    flow = {"nodes": [msg("x", "um"), msg("y", "dois")], "edges": [edge("x", "y")]}
    assert texts(plan_steps(flow)) == ["um", "dois"]


def test_grafo_para_quando_nao_ha_proxima_aresta():
    flow = {"nodes": [msg("a", "um"), msg("b", "solto")], "edges": [], "start": "a"}
    assert texts(plan_steps(flow)) == ["um"]


def test_no_de_mensagem_ignora_arestas_com_branch():
    # De um nó de mensagem só se segue por aresta SEM branch.
    flow = {
        "nodes": [msg("a", "um"), msg("b", "errado"), msg("c", "certo")],
        "edges": [edge("a", "b", "yes"), edge("a", "c")],
        "start": "a",
    }
    assert texts(plan_steps(flow)) == ["um", "certo"]


def test_tipo_desconhecido_e_pulado_e_segue_a_cadeia(caplog):
    flow = {
        "nodes": [msg("a", "um"), {"id": "x", "type": "delay"}, msg("b", "dois")],
        "edges": [edge("a", "x"), edge("x", "b")],
        "start": "a",
    }
    with caplog.at_level(logging.WARNING, logger="inboxpilot.flow"):
        assert texts(plan_steps(flow)) == ["um", "dois"]
    assert "desconhecido" in caplog.text


def test_no_sem_type_e_tratado_como_mensagem():
    flow = {"nodes": [{"id": "a", "text": "oi"}], "edges": [], "start": "a"}
    assert texts(plan_steps(flow)) == ["oi"]


# ── Condição sim/não ────────────────────────────────────────


def _flow_condicao(node: dict) -> dict:
    return {
        "nodes": [msg("m0", "antes"), node, msg("sim", "SIM"), msg("nao", "NÃO")],
        "edges": [edge("m0", "c"), edge("c", "sim", "yes"), edge("c", "nao", "no")],
        "start": "m0",
    }


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Quero o PREÇO, por favor", "SIM"),  # case-insensitive
        ("me manda o link", "NÃO"),
        ("", "NÃO"),
    ],
)
def test_condicao_text_contains(texto, esperado):
    flow = _flow_condicao(cond("c", "text_contains", " Preço "))
    assert texts(plan_steps(flow, {"text": texto})) == ["antes", esperado]


def test_condicao_text_contains_com_valor_vazio_e_falsa():
    flow = _flow_condicao(cond("c", "text_contains", "  "))
    assert texts(plan_steps(flow, {"text": "qualquer coisa"})) == ["antes", "NÃO"]


def test_condicao_sem_mode_usa_text_contains():
    node = {"id": "c", "type": "condition", "value": "oi"}
    assert texts(plan_steps(_flow_condicao(node), {"text": "oi!"})) == ["antes", "SIM"]


@pytest.mark.parametrize(("novo", "esperado"), [(True, "SIM"), (False, "NÃO")])
def test_condicao_is_new_contact(novo, esperado):
    flow = _flow_condicao(cond("c", "is_new_contact"))
    assert texts(plan_steps(flow, {"is_new_contact": novo})) == ["antes", esperado]


def test_condicao_sem_contexto_cai_no_nao():
    flow = _flow_condicao(cond("c", "is_new_contact"))
    assert texts(plan_steps(flow)) == ["antes", "NÃO"]


def test_condicao_modo_desconhecido_cai_no_nao():
    flow = _flow_condicao(cond("c", "tem_tag", "vip"))
    assert texts(plan_steps(flow, {"text": "vip"})) == ["antes", "NÃO"]


def test_condicao_sem_aresta_do_ramo_encerra_o_flow():
    flow = {
        "nodes": [cond("c", "is_new_contact"), msg("sim", "SIM")],
        "edges": [edge("c", "sim", "yes")],  # não há ramo "no"
        "start": "c",
    }
    assert plan_steps(flow, {"is_new_contact": False}) == []
    assert texts(plan_steps(flow, {"is_new_contact": True})) == ["SIM"]


def test_condicao_ignora_aresta_sem_branch():
    flow = {
        "nodes": [cond("c", "is_new_contact"), msg("x", "sem ramo")],
        "edges": [edge("c", "x")],
        "start": "c",
    }
    assert plan_steps(flow, {"is_new_contact": True}) == []


def test_condicoes_encadeadas():
    flow = {
        "nodes": [
            cond("c1", "is_new_contact"),
            cond("c2", "text_contains", "preço"),
            msg("a", "novo+preço"),
            msg("b", "novo sem preço"),
            msg("c", "antigo"),
        ],
        "edges": [
            edge("c1", "c2", "yes"),
            edge("c1", "c", "no"),
            edge("c2", "a", "yes"),
            edge("c2", "b", "no"),
        ],
        "start": "c1",
    }
    assert texts(plan_steps(flow, {"is_new_contact": True, "text": "preço?"})) == ["novo+preço"]
    assert texts(plan_steps(flow, {"is_new_contact": True, "text": "oi"})) == ["novo sem preço"]
    assert texts(plan_steps(flow, {"is_new_contact": False, "text": "preço"})) == ["antigo"]


# ── Nó inexistente ──────────────────────────────────────────


def test_aresta_para_no_inexistente_para_com_o_que_ja_planejou(caplog):
    flow = {"nodes": [msg("a", "um")], "edges": [edge("a", "fantasma")], "start": "a"}
    with caplog.at_level(logging.WARNING, logger="inboxpilot.flow"):
        assert texts(plan_steps(flow)) == ["um"]
    assert "inexistente" in caplog.text


def test_start_inexistente_nao_envia_nada():
    flow = {"nodes": [msg("a", "um")], "edges": [], "start": "nao-existe"}
    assert plan_steps(flow) == []


def test_ramo_de_condicao_para_no_inexistente():
    flow = {
        "nodes": [cond("c", "is_new_contact")],
        "edges": [edge("c", "fantasma", "yes")],
        "start": "c",
    }
    assert plan_steps(flow, {"is_new_contact": True}) == []


# ── Ciclos / MAX_STEPS ──────────────────────────────────────


def test_ciclo_e_cortado_em_max_steps(caplog):
    flow = {
        "nodes": [msg("a", "A"), msg("b", "B")],
        "edges": [edge("a", "b"), edge("b", "a")],
        "start": "a",
    }
    with caplog.at_level(logging.WARNING, logger="inboxpilot.flow"):
        steps = plan_steps(flow)
    assert len(steps) == MAX_STEPS
    assert texts(steps)[:4] == ["A", "B", "A", "B"]
    assert "limite" in caplog.text


def test_auto_loop_em_condicao_termina_sem_enviar():
    flow = {"nodes": [cond("c", "is_new_contact")], "edges": [edge("c", "c", "no")], "start": "c"}
    assert plan_steps(flow, {"is_new_contact": False}) == []


def test_cadeia_maior_que_max_steps_e_truncada():
    flow = chain(*[f"m{i}" for i in range(MAX_STEPS + 5)])
    assert texts(plan_steps(flow)) == [f"m{i}" for i in range(MAX_STEPS)]


def test_respeita_max_steps_alterado(monkeypatch):
    monkeypatch.setattr(flow_runner, "MAX_STEPS", 3)
    assert len(plan_steps(chain(*[str(i) for i in range(10)]))) == 3


# ── Pureza ──────────────────────────────────────────────────


def test_nao_modifica_o_flow_de_entrada():
    import copy

    flow = _flow_condicao(cond("c", "text_contains", "x"))
    original = copy.deepcopy(flow)
    plan_steps(flow, {"text": "x"})
    assert flow == original
